"""Append-only JSONL writer for `chunks.jsonl` + cross-source corroboration.

Satisfies **RESEARCH-09**: cross-source corroboration is automatic — when a
new chunk references a name (gear / artist / external resource) that an
already-ingested chunk also references, `cross_source_match_candidates` is
populated on the new chunk before write.

This is the per-gear knowledge-store writer for `patchbay:research`. It mirrors
the Phase 2 `patchbay:ingest` contract:
  - One JSON object per line, UTF-8, newline-terminated.
  - Append-only at the line level.
  - Real JSON encoder (`json.dumps`) — never raw string concatenation.

SECURITY (T-03-03 — JSONL injection):
  Every line is the output of `json.dumps()` on a structured dict, never
  raw user input concatenated as a string. The encoder JSON-escapes any
  newlines inside string fields, preserving the one-chunk-per-line invariant
  that grep/jq downstream consumers depend on. (Phase 2 finding #2: real
  encoder is required — call it out explicitly. Raw `\n` in strings breaks
  RFC 8259.)

SECURITY (T-03-04 — Path traversal):
  When `gear_root` is provided, the resolved `chunks_jsonl_path` MUST live
  under `gear_root` (via `Path.resolve().relative_to()`). Refuses with
  `ValueError` if the path escapes.
"""

from __future__ import annotations

import copy
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional

try:
    from external_resource_sweep import ensure_external_resource_chunks
except ImportError:  # pragma: no cover — package-relative fallback
    from .external_resource_sweep import ensure_external_resource_chunks  # type: ignore


# ---------------------------------------------------------------------------
# Name extraction for cross-source corroboration
# ---------------------------------------------------------------------------

# Sub-fields inside `content` where named entities live and should be lifted
# out individually. The full set comes from the validated chunk shapes in the
# spike-findings reference (artist_usage, cross_ref, review_section).
_CONTENT_NAME_FIELDS = (
    "artist",
    "from_gear",
    "to_gear",
    "alternatives_recommended",
    "creator",
    "title",
)


# Hard upper bound on `cross_source_match_candidates` per chunk. The
# Phase-3 production smoke surfaced a chunk with a 199-name match cluster:
# a single equipboard `artist_usage` chunk whose `summary` was a plaintext
# megablob of every comma-separated artist name on the page, intersected
# against an existing-chunks haystack that also mentioned every artist.
# Without a cap, the bidirectional TitleCase scan returns hundreds of
# matches. Capping at 25 keeps the field useful as a corroboration hint
# without letting it blow up into a denial-of-readability signal. If you
# need to tune: stay <=50, since the test
# `test_cross_source_matches_caps_runaway_titlecase_blob` pins the upper
# bound.
MAX_NAME_CANDIDATES = 25


def _flatten_strings(value: Any) -> Iterable[str]:
    """Yield every string found anywhere in a nested dict/list structure."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _flatten_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _flatten_strings(v)


def _extract_names_from_content(content: Any) -> List[str]:
    """Extract candidate names from a chunk's `content`.

    Names extracted:
      - If `content` is a string: any TitleCase / multi-word capitalized token
        sequence (heuristic for gear and artist names) AND any URL.
      - If `content` is a dict: the values of `_CONTENT_NAME_FIELDS` (lifted
        verbatim), plus same TitleCase pass over every other string value.
    """
    names: list[str] = []

    if isinstance(content, dict):
        for key in _CONTENT_NAME_FIELDS:
            if key in content:
                val = content[key]
                if isinstance(val, str):
                    names.append(val.strip())
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            names.append(item.strip())
                        elif isinstance(item, dict) and "gear" in item:
                            # e.g., to_gear_top10: [{rank, gear, rating}, ...]
                            g = item.get("gear")
                            if isinstance(g, str):
                                names.append(g.strip())

    # Also scan every string anywhere in content for TitleCase names + URLs.
    title_case_re = re.compile(
        r"\b(?:[A-Z][a-z0-9'’-]+(?:\s+[A-Z][a-z0-9'’-]+)+)\b"
    )
    url_re = re.compile(r"https?://[^\s)\"']+")
    for s in _flatten_strings(content):
        for m in title_case_re.findall(s):
            names.append(m.strip())
        for m in url_re.findall(s):
            names.append(m.strip())

    # Dedupe while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def _stringify_content(content: Any) -> str:
    """Flatten a chunk's `content` (string or dict) into one searchable string."""
    return " ".join(s for s in _flatten_strings(content))


def compute_cross_source_matches(
    new_chunk: dict,
    existing_chunks: list[dict],
) -> list[str]:
    """Return deduplicated names that BOTH `new_chunk` and at least one
    `existing_chunks` entry reference.

    The match is bidirectional: a name extracted from `new_chunk.content`
    counts if it appears anywhere in any existing chunk's stringified
    content, AND a name extracted from an existing chunk counts if it
    appears anywhere in `new_chunk`'s stringified content. This catches
    possessive variants (`Rhett Shull` vs `Rhett Shull's`) and partial-
    reference variants that a one-directional scan misses.

    Powers `cross_source_match_candidates`. Trivial implementation per the
    spike-findings: maintain a per-gear "all referenced names" set across
    all chunks; on each new chunk, intersect against the existing set.
    """
    new_names = _extract_names_from_content(new_chunk.get("content"))
    new_haystack = _stringify_content(new_chunk.get("content"))

    existing_haystack = " ".join(
        _stringify_content(c.get("content")) for c in existing_chunks
    )

    matches: list[str] = []
    seen: set[str] = set()

    # Direction A: names lifted from the new chunk that exist in any prior chunk.
    for name in new_names:
        if len(matches) >= MAX_NAME_CANDIDATES:
            break
        if name in seen:
            continue
        if name in existing_haystack:
            matches.append(name)
            seen.add(name)

    # Direction B: names lifted from prior chunks that reappear in the new chunk.
    for chunk in existing_chunks:
        if len(matches) >= MAX_NAME_CANDIDATES:
            break
        for name in _extract_names_from_content(chunk.get("content")):
            if len(matches) >= MAX_NAME_CANDIDATES:
                break
            if name in seen:
                continue
            if name in new_haystack:
                matches.append(name)
                seen.add(name)

    return matches


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def _validate_path_containment(
    chunks_jsonl_path: str,
    gear_root: Optional[str],
) -> Path:
    """Resolve `chunks_jsonl_path` and ensure it lives under `gear_root`.

    Uses `Path.is_relative_to` when available (Python 3.9+ provides it on
    3.9+, but the plugin's interpreter floor is 3.9.6 stdlib where it was
    added in 3.9 — we still keep a `relative_to()`-based fallback for any
    older runtime). T-03-04 mitigation.
    """
    resolved = Path(chunks_jsonl_path).resolve()
    if gear_root is not None:
        gear_root_resolved = Path(gear_root).resolve()
        if hasattr(resolved, "is_relative_to"):
            contained = resolved.is_relative_to(gear_root_resolved)
        else:
            try:
                resolved.relative_to(gear_root_resolved)
                contained = True
            except ValueError:
                contained = False
        if not contained:
            raise ValueError(
                f"Refusing to write chunks.jsonl at {resolved}: path is outside "
                f"gear_root {gear_root_resolved}."
            )
    return resolved


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def _read_existing(chunks_path: Path) -> list[dict]:
    if not chunks_path.exists():
        return []
    lines = chunks_path.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # Corrupt line — surface the path so the caller can offer .bak rescue.
            raise ValueError(
                f"chunks.jsonl at {chunks_path} contains a non-JSON line. "
                f"Refusing to append until the file is repaired."
            )
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_chunks(
    chunks_jsonl_path: str,
    new_chunks: list[dict],
    gear_root: Optional[str] = None,
    *,
    trust: Optional[str] = None,
) -> dict:
    """Append `new_chunks` to `chunks_jsonl_path`, populating cross-source matches.

    For each new chunk:
      1. Compute `cross_source_match_candidates` against existing chunks +
         every new chunk already written in this batch.
      2. Append the chunk as a single `json.dumps` line.

    `trust` (Plan 04-03, CITATION-03): when a non-empty string is supplied,
    every emitted chunk is stamped with `chunk["trust"] = trust` BEFORE the
    JSONL append. Used by verify_resource to promote chunks to high-trust on
    user-marked verified resources. Empty string or None = no stamping
    (backward-compatible with all Phase 3 + Plan 04-01 callers).

    Returns `{"written": N, "matched": M}` where M counts chunks with at least
    one cross-source match.
    """
    resolved = _validate_path_containment(chunks_jsonl_path, gear_root)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    existing = _read_existing(resolved)
    written = 0
    matched = 0

    with open(resolved, "a", encoding="utf-8") as f:
        for raw_chunk in new_chunks:
            chunk = copy.deepcopy(raw_chunk)
            # Plan 04-03: stamp trust at the top level when a non-empty
            # string is supplied. Empty string = no stamping (treated like
            # None) so callers can pass through an optional config value
            # without a None-check.
            if isinstance(trust, str) and trust:
                chunk["trust"] = trust
            matches = compute_cross_source_matches(chunk, existing)
            chunk["cross_source_match_candidates"] = matches
            if matches:
                matched += 1
            # JSON-encoded line — never raw concat. T-03-03 mitigation.
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            existing.append(chunk)
            written += 1

    # CITATION-01 + CITATION-04: post-append sweep guarantees every
    # external URL referenced from any chunk has exactly one
    # external_resource chunk with canonical .url and complete
    # citing_chunk_ids. Sweep failure surfaces (no try/except wrapper)
    # because data-layer integrity beats silent partial writes.
    ensure_external_resource_chunks(str(resolved), gear_root=gear_root)

    return {"written": written, "matched": matched}


def update_chunk_field(
    chunks_jsonl_path: str,
    chunk_id: str,
    field_path: str,
    new_value: Any,
    gear_root: Optional[str] = None,
) -> None:
    """Rewrite a single chunk's field in place by `chunk_id` + dotted `field_path`.

    Reads the JSONL, locates the chunk whose `id == chunk_id`, mutates the
    field via dotted path (e.g., `content.frame_description`), then atomically
    rewrites the file via a temp file + `os.replace`. Used by the YouTube
    two-pass enrichment in Plan 04 (first pass writes the multimodal_segment;
    second pass enriches `content.frame_description` after vision review).

    Raises ValueError if the chunk_id is not found.
    """
    resolved = _validate_path_containment(chunks_jsonl_path, gear_root)
    if not resolved.exists():
        raise FileNotFoundError(f"chunks.jsonl not found at {resolved}")

    chunks = _read_existing(resolved)
    found = False
    parts = field_path.split(".")
    for chunk in chunks:
        if chunk.get("id") != chunk_id:
            continue
        # Walk to the parent of the target leaf.
        target: Any = chunk
        for key in parts[:-1]:
            if not isinstance(target, dict) or key not in target:
                raise KeyError(
                    f"field_path {field_path!r} not navigable on chunk {chunk_id}"
                )
            target = target[key]
        if not isinstance(target, dict):
            raise TypeError(
                f"field_path {field_path!r} parent is not a dict on chunk {chunk_id}"
            )
        target[parts[-1]] = new_value
        found = True
        break

    if not found:
        raise ValueError(f"chunk id {chunk_id!r} not found in {resolved}")

    # Atomic rewrite: write a sibling temp file, then `os.replace`.
    fd, tmp_path = tempfile.mkstemp(
        prefix=".chunks.", suffix=".jsonl", dir=str(resolved.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        os.replace(tmp_path, resolved)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
