"""external_resource_sweep — post-write idempotent sweep that guarantees
CITATION-01 (every URL referenced from any chunk in chunks.jsonl has
exactly one external_resource chunk with populated citing_chunk_ids) and
CITATION-04 (URLs stored on external_resource chunks are canonical).

Called by `write_chunks` at the END of every append. Reads chunks.jsonl,
computes the citation graph keyed by canonical URL, rewrites chunks.jsonl
atomically via tempfile.mkstemp + os.replace.

Locked design decisions at v2.0:
  - tier_used on sweep-emitted chunks = None (NOT 0). The spike-findings
    tier ladder reserves tier_used=0 for "manual user-paste (escape
    hatch)" — a sweep-emitted chunk is the OPPOSITE of that (synthetic,
    derived from URLs in OTHER chunks; no fetch, no paste). Downstream
    consumers treat None as "did not fetch."
  - source = "sweep" on emitted chunks (audit trail; does not masquerade
    as a source-class emission).
  - id = "ext-sweep-{sha1(canonical_url)[:8]}" — STABLE across re-runs.
    W5 mitigation: a monotonic counter would re-issue the same id for a
    DIFFERENT canonical URL when discovery order changes; a hash-based
    id is content-derived and round-trip-stable, which Plan 02's
    Recommendation.external_resource_chunk_id depends on.
  - resource_type is AUTHORITATIVELY classified by `_classify_resource_type`
    and OVERWRITES on merge (reddit.py emits "article" for reddit-post
    URLs; the sweep emits "reddit-post" and overwrites). Tech debt: a
    follow-up could extract a shared classify_url helper used by both
    reddit.py and the sweep; for Phase 4 the sweep override is the
    load-bearing fix.

Threats addressed:
  - T-04-01 (Tampering / non-http(s) schemes): canonicalize_url returns
    "" for javascript:/data:/file: schemes; the sweep discards empty.
  - T-04-02 (Spoofing / source-class duplicate-spam): dedup is keyed on
    canonical URL, not raw URL. ?si=a / ?si=b variants collapse.
  - T-04-04 (DoS / partial write): atomic rewrite via tempfile.mkstemp +
    os.replace (mirrors update_chunk_field's idiom). A crash mid-rewrite
    leaves the original chunks.jsonl intact.
  - T-04-05 (provenance.url tampering): provenance.url is canonicalized
    + scheme-checked identically to content URLs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from canonicalize_url import canonicalize_url
except ImportError:  # pragma: no cover — package-relative fallback
    from .canonicalize_url import canonicalize_url  # type: ignore


# Permissive http(s) URL regex. Trailing punctuation like .,;:!?) is
# stripped before canonicalization (URLs in prose often end at sentence
# punctuation, not at the URL boundary).
URL_RE = re.compile(r"https?://[^\s<>\"'\\)]+", re.IGNORECASE)


def _classify_resource_type(url: str) -> str:
    """Sweep's AUTHORITATIVE resource_type classifier.

    Overrides any value set by a source-class parser on merge (e.g.,
    reddit.py emits "article" for reddit-post URLs because its
    `_classify_url` does not know the "reddit-post" type; the sweep
    emits "reddit-post" and overwrites).

    Locked at v2.0; a future refactor could extract a shared classify_url
    helper used by both this module and reddit.py.
    """
    u = url.lower()
    if "youtube.com/watch" in u or "youtu.be/" in u:
        return "youtube"
    if "reddit.com/r/" in u and "/comments/" in u:
        return "reddit-post"
    if u.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        return "image"
    return "article"


def _sweep_id(canonical_url: str) -> str:
    """Stable, content-derived id for a sweep-emitted external_resource.

    SHA-1 truncated to 8 hex chars (~4 billion buckets — collision
    probability on a per-gear chunks.jsonl of <10k external_resource
    chunks is negligible per the birthday-paradox floor).

    W5 mitigation: a monotonic counter would re-issue the same id for a
    DIFFERENT URL across runs when discovery order changes. Hash-based
    ids are round-trip-stable, which Plan 02's
    Recommendation.external_resource_chunk_id (and Plan 03's verify
    lookup) depend on.
    """
    return "ext-sweep-" + hashlib.sha1(
        canonical_url.encode("utf-8")
    ).hexdigest()[:8]


def _walk_strings(value: Any) -> Iterable[str]:
    """Yield every string found anywhere in a nested dict/list structure."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk_strings(v)


def extract_urls_from_chunk(chunk: dict) -> list[str]:
    """Return canonical URLs referenced by a non-external_resource chunk.

    Surfaces:
      - chunk["content"] recursively (strings inside dicts/lists)
      - chunk["provenance"]["url"]      (page URL — counts as a citation)
      - chunk["provenance"]["deep_link"] (segment-level deep link)

    For external_resource chunks: returns [] (those are handled separately
    by the sweep — see `ensure_external_resource_chunks`).
    """
    if chunk.get("type") == "external_resource":
        return []
    urls: list[str] = []
    for s in _walk_strings(chunk.get("content")):
        urls.extend(URL_RE.findall(s))
    prov = chunk.get("provenance") or {}
    for key in ("url", "deep_link"):
        val = prov.get(key)
        if isinstance(val, str) and val:
            urls.append(val)
    out: list[str] = []
    seen: set[str] = set()
    for u in urls:
        # Strip trailing punctuation that commonly trails URLs in prose.
        canonical = canonicalize_url(u.rstrip(".,;:!?)"))
        if canonical and canonical not in seen:
            seen.add(canonical)
            out.append(canonical)
    return out


def ensure_external_resource_chunks(
    chunks_jsonl_path,
    gear_root: Optional[str] = None,
) -> None:
    """Idempotent post-write sweep. Reads chunks.jsonl, builds the citation
    graph keyed by canonical URL, rewrites chunks.jsonl atomically.

    Signature mirrors write_chunks: path FIRST (positional), gear_root
    keyword with default. The sweep currently does not use gear_root
    (write_chunks already validated the path before invoking the sweep)
    but the param is accepted for signature parity and future hardening.

    Args:
        chunks_jsonl_path: Path to the chunks.jsonl file (str or Path).
        gear_root: Reserved for future path-containment hardening; ignored
            today.
    """
    chunks_path = Path(chunks_jsonl_path)
    if not chunks_path.exists():
        return

    rows: list[dict] = []
    with chunks_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # Defense-in-depth: Plan 03-01's _read_existing raises on
                # malformed lines, so this branch should not trigger in
                # production. Skip rather than crash the sweep — the file
                # is already corrupt and the caller's repair flow handles it.
                continue

    # Build citation graph from non-external_resource chunks.
    url_to_citing: dict[str, set[str]] = {}
    for chunk in rows:
        if chunk.get("type") == "external_resource":
            continue
        chunk_id = chunk.get("id")
        if not chunk_id:
            continue
        for url in extract_urls_from_chunk(chunk):
            url_to_citing.setdefault(url, set()).add(chunk_id)

    # Canonicalize + merge existing external_resource chunks.
    # NB: write_chunk.compute_cross_source_matches is NAME-based not id-
    # based (verified against L135-L186), so dropping a duplicate
    # external_resource by id is safe — no other chunk's match-candidates
    # field references the dropped id.
    existing: dict[str, dict] = {}  # canonical_url -> chunk dict
    kept_non_ext: list[dict] = []
    for chunk in rows:
        if chunk.get("type") != "external_resource":
            kept_non_ext.append(chunk)
            continue
        content = chunk.get("content") or {}
        raw_url = content.get("url", "") or ""
        canonical = canonicalize_url(raw_url)
        if not canonical:
            # Unusable URL — drop the chunk (it cannot be cited).
            continue
        if canonical in existing:
            # Duplicate external_resource for the same canonical URL.
            # Merge citing_chunk_ids; keep the FIRST occurrence's id and
            # remaining fields (preserves Equipboard's parent backlink).
            prior = existing[canonical]
            prior_cids = set(prior["content"].get("citing_chunk_ids") or [])
            new_cids = set(content.get("citing_chunk_ids") or [])
            prior["content"]["citing_chunk_ids"] = sorted(prior_cids | new_cids)
            continue
        # Write canonical URL back to the chunk.
        content["url"] = canonical
        # AUTHORITATIVE override of resource_type — the sweep's classifier
        # wins on merge (reddit.py emits "article" for reddit-post URLs;
        # the sweep emits "reddit-post" and overwrites here).
        content["resource_type"] = _classify_resource_type(canonical)
        chunk["content"] = content
        existing[canonical] = chunk

    # Update citing_chunk_ids on existing external_resource chunks.
    for url, chunk in existing.items():
        prior = set(chunk["content"].get("citing_chunk_ids") or [])
        discovered = url_to_citing.get(url, set())
        chunk["content"]["citing_chunk_ids"] = sorted(prior | discovered)

    # Append new external_resource chunks for canonical URLs without one.
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    new_ext: list[dict] = []
    for url, citing in url_to_citing.items():
        if url in existing:
            continue
        new_ext.append({
            "id": _sweep_id(url),
            "type": "external_resource",
            "source": "sweep",
            "content": {
                "resource_type": _classify_resource_type(url),
                "creator": "",
                "title": "",
                "url": url,
                "updated": None,
                "relevance": "",
                "citing_chunk_ids": sorted(citing),
            },
            # tier_used = None: the sweep does NOT fetch — this chunk is
            # synthetic, derived from URLs in OTHER chunks. The spike-
            # findings tier ladder reserves tier_used=0 for "manual user-
            # paste (escape hatch)" which is a DIFFERENT semantic.
            # Downstream queries treat null as "did not fetch."
            "tier_used": None,
            "provenance": {
                "url": url,
                "scraped_at": now_iso,
            },
        })

    # Sort new_ext by id so the file is deterministically ordered across
    # re-runs (hash-based ids give cross-run id stability, but sorting
    # also prevents dict-iteration-order differences from surfacing as
    # byte-level diffs and breaking idempotency tests).
    new_ext.sort(key=lambda c: c["id"])

    # Atomically rewrite: non-ext chunks (in original order) + existing
    # ext chunks (in original canonical-URL insertion order) + new ext
    # chunks (id-sorted).
    all_rows = (
        kept_non_ext
        + [existing[u] for u in existing]
        + new_ext
    )
    fd, tmp_path = tempfile.mkstemp(
        prefix=".chunks-sweep-", dir=str(chunks_path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_fp:
            for row in all_rows:
                tmp_fp.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp_path, chunks_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
