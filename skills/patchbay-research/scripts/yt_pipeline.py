"""YouTube ingestion pipeline orchestration.

Tier-1 fetch for YouTube is not a static HTML GET (YouTube's `/watch` pages
are JS-heavy and unhelpful as static HTML). Instead the pipeline:

  1. `fetch_video_assets(url, tempdir)` — invokes `yt-dlp` twice:
        a. Auto-captions only: produces `<tempdir>/video.<lang>.vtt`.
        b. 720p video download: produces `<tempdir>/video.mp4`.
  2. `parse_vtt(vtt_path)` — list of `{start, end, text, timestamp_display}` windows.
  3. `sample_frames(mp4_path, frames_dir)` — `ffmpeg fps=1/30` -> N .jpg files.
  4. `build_multimodal_chunks(caption_windows, frame_paths, gear_ctx, url, vid)` —
     zips caption windows with frame paths into `multimodal_segment` chunks,
     each carrying the placeholder `<<PENDING_READ_TOOL_DESCRIPTION>>` plus
     `provenance.frame_path`. The SKILL driver's second pass Reads each
     frame and overwrites the placeholder via `write_chunk.update_chunk_field`.
  5. Any leftover caption windows beyond the frame count are emitted as
     `transcript` chunks (no frame).

SECURITY (T-03-20, T-03-21, T-03-22, T-03-25):
  - Every subprocess.run uses `shell=False` with an argv list — URLs are
    passed as a single argv element, NEVER interpolated into a shell string.
  - Tempdirs are created via `tempfile.mkdtemp(prefix="patchbay-yt-")` —
    system temp, never under gear_root. Cleanup via `shutil.rmtree` is the
    caller's responsibility (the source class wraps this in try/finally).
  - Subprocess timeouts: 600s (yt-dlp) / 300s (ffmpeg).
  - No Whisper anywhere; auto-captions are the only audio-text layer.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

# Import parse_vtt under a wrapper alias so tests can monkeypatch the
# pipeline's caption-parsing step without monkeypatching the parser module
# itself (keeps parse_vtt unit tests isolated from pipeline tests).
try:
    from scripts.parse_vtt import parse_vtt as _real_parse_vtt  # type: ignore
except ImportError:  # pragma: no cover — fallback for unusual layouts
    _RESEARCH_ROOT = Path(__file__).resolve().parent.parent
    if str(_RESEARCH_ROOT) not in sys.path:
        sys.path.insert(0, str(_RESEARCH_ROOT))
    from scripts.parse_vtt import parse_vtt as _real_parse_vtt  # type: ignore


YT_DLP_TIMEOUT_SEC = 600
FFMPEG_TIMEOUT_SEC = 300

# Sentinel string that the SKILL.md two-pass enrichment loop replaces.
PENDING_READ_TOOL_DESCRIPTION = "<<PENDING_READ_TOOL_DESCRIPTION>>"


# ---------------------------------------------------------------------------
# Tempdir helper (kept thin so tests can monkeypatch tempfile.mkdtemp)
# ---------------------------------------------------------------------------

def make_tempdir() -> str:
    """Create a per-run tempdir under the system temp area.

    T-03-22 mitigation: the prefix is `patchbay-yt-` and the dir lands in
    `tempfile.gettempdir()` — NEVER under the user's gear_root.
    """
    return tempfile.mkdtemp(prefix="patchbay-yt-")


# ---------------------------------------------------------------------------
# yt-dlp asset fetcher
# ---------------------------------------------------------------------------

def fetch_video_assets(url: str, tempdir: str) -> dict:
    """Invoke `yt-dlp` twice to pull captions + 720p video.

    Returns `{vtt_path, mp4_path, video_id}`. Either path may be `None` if
    the corresponding download did not produce a file. The function does not
    raise on subprocess non-zero return — callers decide whether the lack of
    one asset is fatal.

    Raises `FileNotFoundError` if `yt-dlp` is not on PATH. The source class
    catches this and degrades to logging a failures.log entry.
    """
    td = Path(tempdir)
    td.mkdir(parents=True, exist_ok=True)

    # 1. Auto-captions only (no video download).
    subprocess.run(
        [
            "yt-dlp",
            "--write-auto-subs",
            "--skip-download",
            "--sub-format",
            "vtt",
            "--sub-lang",
            "en",
            "-o",
            str(td / "video"),
            url,
        ],
        shell=False,
        check=False,
        timeout=YT_DLP_TIMEOUT_SEC,
        capture_output=True,
    )

    # 2. 720p video download.
    subprocess.run(
        [
            "yt-dlp",
            "-f",
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",
            "--merge-output-format",
            "mp4",
            "--output",
            str(td / "video.mp4"),
            url,
        ],
        shell=False,
        check=False,
        timeout=YT_DLP_TIMEOUT_SEC,
        capture_output=True,
    )

    # Resolve actual filenames.
    vtt_candidates = sorted(td.glob("video.*.vtt"))
    vtt_path: Optional[str] = str(vtt_candidates[0]) if vtt_candidates else None
    mp4_path: Optional[str] = str(td / "video.mp4") if (td / "video.mp4").exists() else None

    return {
        "vtt_path": vtt_path,
        "mp4_path": mp4_path,
        "video_id": _extract_video_id(url),
    }


def _extract_video_id(url: str) -> str:
    """Extract the YouTube video id from a /watch?v= or youtu.be/ URL.

    Returns the validated id or "unknown" on parse failure. T-03-21
    mitigation: id must match `^[A-Za-z0-9_-]{6,20}$` so a crafted query
    value can never be smuggled into a downstream argv.
    """
    from urllib.parse import urlparse, parse_qs

    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return "unknown"

    host = (parsed.hostname or "").lower()
    candidate: Optional[str] = None

    if host == "youtu.be":
        candidate = (parsed.path or "").lstrip("/")
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        qs = parse_qs(parsed.query or "")
        v = qs.get("v") or []
        candidate = v[0] if v else None

    if not candidate or not re.match(r"^[A-Za-z0-9_-]{6,20}$", candidate):
        return "unknown"
    return candidate


# ---------------------------------------------------------------------------
# ffmpeg frame sampler
# ---------------------------------------------------------------------------

def sample_frames(mp4_path: str, frames_dir) -> List[str]:
    """Sample one frame every 30 seconds via ffmpeg.

    Returns the sorted list of resulting `frame_NNN.jpg` paths. If `ffmpeg`
    raises `FileNotFoundError`, returns `[]` so the source class can fall
    back to transcript-only chunks (degraded mode).
    """
    fd = Path(frames_dir)
    fd.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(mp4_path),
                "-vf",
                "fps=1/30",
                "-q:v",
                "3",
                str(fd / "frame_%03d.jpg"),
            ],
            shell=False,
            check=False,
            timeout=FFMPEG_TIMEOUT_SEC,
            capture_output=True,
        )
    except FileNotFoundError:
        return []

    return [str(p) for p in sorted(fd.glob("frame_*.jpg"))]


# ---------------------------------------------------------------------------
# parse_vtt indirection (for tests)
# ---------------------------------------------------------------------------

def _parse_vtt_safe(vtt_path: Optional[str], window_seconds: int = 30) -> List[dict]:
    """Wrap `parse_vtt` so it tolerates a missing path. Tests monkeypatch this
    to inject fake caption windows without touching the real parser."""
    if not vtt_path:
        return []
    if not Path(vtt_path).exists():
        return []
    return _real_parse_vtt(vtt_path, window_seconds=window_seconds)


# ---------------------------------------------------------------------------
# Multimodal-chunk builder
# ---------------------------------------------------------------------------

def _deep_link(video_url: str, video_id: str, start_seconds: float) -> str:
    """Compose a deep-link URL with `&t=Xs` (or `?t=Xs` for youtu.be)."""
    secs = int(start_seconds)
    if "youtu.be/" in video_url:
        # canonical: https://youtu.be/<id>?t=Xs
        return f"https://youtu.be/{video_id}?t={secs}s"
    sep = "&" if "?" in video_url else "?"
    return f"{video_url}{sep}t={secs}s"


def build_multimodal_chunks(
    caption_windows: List[dict],
    frame_paths: List[str],
    gear_ctx: dict,
    video_url: str,
    video_id: str,
) -> List[dict]:
    """Zip caption windows with frame paths into chunks.

    Per the plan:
      - Each `(window, frame)` pair produces one `multimodal_segment` chunk
        with `frame_description = <<PENDING_READ_TOOL_DESCRIPTION>>` (the
        SKILL driver's second pass enrichment replaces this).
      - Each caption window also produces one `transcript` chunk.
      - Caption windows beyond the frame count get only their `transcript`
        chunk (no multimodal, since there's no frame to pair).

    Every chunk: `source: "youtube"`, `tier_used: 1`, provenance with
    `url`, `deep_link`, `timestamp_display`, `scraped_at`. multimodal_segment
    chunks additionally carry `provenance.frame_path` (the absolute path the
    SKILL driver Reads from during enrichment).
    """
    scraped_at = gear_ctx.get("scraped_at", "")
    chunks: List[dict] = []
    counter = 1

    def _next_id(prefix: str) -> str:
        nonlocal counter
        cid = f"yt-{video_id}-{prefix}-{counter:03d}"
        counter += 1
        return cid

    for idx, window in enumerate(caption_windows):
        start = float(window.get("start", 0.0))
        end = float(window.get("end", start))
        text = window.get("text", "")
        ts_display = window.get("timestamp_display", "")
        deep_link = _deep_link(video_url, video_id, start)
        base_prov = {
            "url": video_url,
            "deep_link": deep_link,
            "timestamp_display": ts_display,
            "scraped_at": scraped_at,
        }

        # transcript chunk (always emitted per window).
        chunks.append(
            {
                "id": _next_id("transcript"),
                "type": "transcript",
                "source": "youtube",
                "content": {
                    "start_time": start,
                    "end_time": end,
                    "text": text,
                },
                "tier_used": 1,
                "provenance": dict(base_prov),
            }
        )

        # multimodal_segment chunk — only if a frame is available at this index.
        if idx < len(frame_paths):
            frame_path = frame_paths[idx]
            mm_prov = dict(base_prov)
            mm_prov["frame_path"] = frame_path
            chunks.append(
                {
                    "id": _next_id("mm"),
                    "type": "multimodal_segment",
                    "source": "youtube",
                    "content": {
                        "timestamp": start,
                        "frame": Path(frame_path).name,
                        "frame_description": PENDING_READ_TOOL_DESCRIPTION,
                        "caption_text": text,
                        "what_audio_misses": "",
                    },
                    "tier_used": 1,
                    "provenance": mm_prov,
                }
            )

    return chunks
