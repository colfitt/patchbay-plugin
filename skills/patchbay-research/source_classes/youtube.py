"""YouTube source class — the multimodal-secondary pipeline.

Tier-1 fetch for YouTube does NOT do a static HTML GET. The `/watch` page
is JS-heavy and unhelpful; instead this module returns a sentinel
`{status: 0, body: "", json: None, url_attempted, needs_pipeline: True}`,
and the SKILL driver dispatches straight to `parse_to_chunks`, which
orchestrates the yt-dlp + parse_vtt + ffmpeg + Read-tool-vision pipeline
described in `references/source-class-youtube.md` and spike 002c.

NO Whisper anywhere — auto-captions are the audio-text layer (RESEARCH-07).

SECURITY mitigations (from the plan's threat register):
  - T-03-20: every `subprocess.run` invocation is `shell=False` with an
    argv list; the URL is passed as a single argv element (never a string).
  - T-03-21: the extracted video_id is validated against
    `^[A-Za-z0-9_-]{6,20}$` before reuse in deep_links/chunk_ids.
  - T-03-22: the per-run tempdir is created via
    `tempfile.mkdtemp(prefix="patchbay-yt-")` — system temp, NEVER under the
    user's gear_root. Cleaned up via `shutil.rmtree` in try/finally.
  - T-03-24: `match_url` rejects non-http(s) schemes and uses exact-host
    set membership.
"""

from __future__ import annotations

import re
import shutil
import sys
from typing import Optional
from urllib.parse import urlparse, parse_qs

# yt_pipeline lives next to this module on sys.path (the test harness +
# the SKILL driver both ensure `skills/patchbay-research` is importable).
try:
    from scripts import yt_pipeline  # type: ignore
except ImportError:  # pragma: no cover — fallback for unusual layouts
    from ..scripts import yt_pipeline  # type: ignore


# ---------------------------------------------------------------------------
# URL matching
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = frozenset(
    {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}
)
ALLOWED_SCHEMES = frozenset({"http", "https"})
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


def match_url(url: str) -> bool:
    """True iff `url` is a YouTube watch URL (long-form or youtu.be short-form).

    Scheme MUST be http or https (T-03-24). Host MUST be an exact match
    against `ALLOWED_HOSTS` (T-03-24). Path must satisfy one of:
      (a) `/watch` with a `v` query param, or
      (b) host is `youtu.be` and path is `/<id>` (id non-empty).
    """
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False
    host = (parsed.netloc or "").lower()
    if host not in ALLOWED_HOSTS:
        return False

    if host == "youtu.be":
        path = (parsed.path or "").lstrip("/")
        if not path:
            return False
        # Drop any extra trailing path segments — accept first segment id-shaped.
        first_seg = path.split("/", 1)[0]
        return bool(first_seg)

    # youtube.com variants
    if parsed.path != "/watch":
        return False
    qs = parse_qs(parsed.query or "")
    return bool(qs.get("v"))


# ---------------------------------------------------------------------------
# Tier-1 fetch (sentinel: no static GET for YouTube)
# ---------------------------------------------------------------------------

def fetch_tier1(url: str) -> dict:
    """Return a sentinel signaling that the SKILL driver should call
    `parse_to_chunks` directly (no tier-1 HTTP fetch happens for YouTube).
    """
    return {
        "status": 0,
        "body": "",
        "json": None,
        "url_attempted": url,
        "needs_pipeline": True,
        "headers": {},
        "elapsed_ms": 0,
        "exc": None,
    }


# ---------------------------------------------------------------------------
# parse_to_chunks orchestration
# ---------------------------------------------------------------------------

# When yt-dlp is missing, parse_to_chunks records a structured failure here
# so the SKILL driver can forward it to `failures.log` via the Plan 01
# `log_failure` helper.
last_failure_record: Optional[dict] = None


def _record_failure(url: str, reason: str, detail: str, escalation) -> None:
    global last_failure_record
    last_failure_record = {
        "url": url,
        "reason": reason,
        "reason_detail": detail,
        "suggested_escalation": escalation,
    }


def _video_id_from_url(url: str) -> str:
    """Extract video id with strict validation (T-03-21). Returns 'unknown' on miss."""
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return "unknown"
    host = (parsed.hostname or "").lower()
    candidate: Optional[str] = None
    if host == "youtu.be":
        candidate = (parsed.path or "").lstrip("/").split("/", 1)[0]
    elif host in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
        qs = parse_qs(parsed.query or "")
        v = qs.get("v") or []
        candidate = v[0] if v else None
    if not candidate or not _VIDEO_ID_RE.match(candidate):
        return "unknown"
    return candidate


def parse_to_chunks(fetch_result: dict, gear_ctx: dict) -> list[dict]:
    """Drive the yt-dlp + parse_vtt + ffmpeg pipeline; emit chunks.

    Returns `[]` if yt-dlp is missing on PATH (also records a failure detail
    so the SKILL driver can forward it to failures.log). Otherwise returns:
      - one `transcript` chunk per caption window, AND
      - one `multimodal_segment` chunk per (caption_window, frame_path) pair
        with `content.frame_description == "<<PENDING_READ_TOOL_DESCRIPTION>>"`
        and `provenance.frame_path` set to the on-disk .jpg path. The SKILL
        driver's second-pass loop Reads each frame and calls
        `write_chunk.update_chunk_field` to overwrite the placeholder.

    If ffmpeg is missing, the pipeline degrades to transcript chunks only.
    """
    global last_failure_record
    last_failure_record = None

    url = fetch_result.get("url_attempted") or ""
    video_id = _video_id_from_url(url)

    tempdir = yt_pipeline.make_tempdir()
    try:
        try:
            assets = yt_pipeline.fetch_video_assets(url, tempdir)
        except FileNotFoundError:
            _record_failure(
                url,
                reason="other",
                detail="yt-dlp not installed (PATH lookup failed)",
                escalation="skip",
            )
            return []

        caption_windows = yt_pipeline._parse_vtt_safe(assets.get("vtt_path"))

        # ffmpeg frame sampling. sample_frames already swallows FileNotFoundError
        # and returns [] — degraded mode is just transcripts.
        frame_paths = []
        mp4 = assets.get("mp4_path")
        if mp4:
            frame_paths = yt_pipeline.sample_frames(mp4, f"{tempdir}/frames")

        chunks = yt_pipeline.build_multimodal_chunks(
            caption_windows=caption_windows,
            frame_paths=frame_paths,
            gear_ctx=gear_ctx,
            video_url=url,
            video_id=video_id,
        )
        return chunks
    finally:
        # NEVER leak the tempdir. Frame paths emitted in chunks reference
        # files inside this dir — the SKILL driver MUST complete the Read
        # tool enrichment pass BEFORE control returns from the research
        # run, because cleanup happens here. (Documented in SKILL.md.)
        shutil.rmtree(tempdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Self-registration (idempotent)
# ---------------------------------------------------------------------------
# Per source-class-registry.md, each module appends itself to REGISTRY on
# import. Guarded against double-registration so importlib.reload() in tests
# does not duplicate the entry. Copied verbatim from `reddit.py` / `equipboard.py`.

from . import REGISTRY as _REGISTRY  # noqa: E402

_self = sys.modules[__name__]
if _self not in _REGISTRY:
    _REGISTRY.append(_self)
