"""citations.py — Citation-recommendation aggregator + markdown formatter
+ CLI entry point for ``/patchbay:research --citations <gear>``.

CITATION-02 deliverable (Plan 04-02). Consumes the substrate that
Plan 04-01's `external_resource_sweep` guarantees on every `write_chunks`
call:

  - Every external `http(s)` URL referenced from any chunk in
    `chunks.jsonl` has exactly one `external_resource` chunk whose
    `content.url` is canonical and whose `content.citing_chunk_ids[]`
    lists every chunk that references that URL.

This module reads `chunks.jsonl`, groups `external_resource` chunks by
canonical URL, applies an N-threshold over the count of DISTINCT
citing-chunk source values (NOT the raw length of
`citing_chunk_ids`), and emits either a markdown block (default) or a
JSON array (with `--json`) to stdout.

Distinct-source rule
====================

The CITATION-02 spec says "N independent sources reference the same
canonicalized URL". The load-bearing rule:

  - Count the DISTINCT `citing_chunk["source"]` values across the
    chunks named in `citing_chunk_ids`. NOT the raw length.
  - The external_resource chunk's OWN `source` field is NOT counted
    — only the sources of its citing chunks.
  - Citing-chunk references to other `external_resource` chunks are
    IGNORED (an external_resource is a citation TARGET, not a SOURCE
    — counting it as a vote would inflate the threshold from inside
    the citation graph itself).

Rationale: a single Reddit thread (one source) emitting two
external_resource references to the same YouTube video should NOT
trip a threshold of 2. Two INDEPENDENT sources (e.g., reddit +
equipboard) referencing the same video SHOULD trip it.

Known v2.0 limitation (deferred to a future phase per W4 of the plan
revision context): when same-class chunks dominate, the distinct-
source count may under-represent true independence. Example: an
Equipboard page that re-publishes a YouTube reviewer's transcript is
ONE source ("equipboard") in the count, even though the underlying
primary sources are two. Proper primary-source-independence tracking
(a `primary_sources: list[str]` field on citing chunks capturing the
upstream re-published sources) is deferred.

CLI surface
===========

Invocation (typically via the SKILL.md dispatch):

  python3 skills/patchbay-research/scripts/citations.py \\
      <chunks_path> --gear "<Brand Item>" \\
      [--threshold N] [--filter-url URL] [--json]

Flags:
  --threshold N        int >= 1; default is the value of the
                       PATCHBAY_CITATION_THRESHOLD env var if it is a
                       positive integer, else 2. The CLI flag wins.
  --filter-url URL     Show only recommendations whose canonical URL
                       matches the canonicalized form of URL.
  --json               Emit a JSON array of Recommendation dicts to
                       stdout instead of the markdown block.

Exit code: 0 on success (INCLUDING the no-results case). Non-zero is
reserved for argument-parsing errors raised by argparse.

Locked empty-result message (per W3 — the user has just run
/patchbay:research to populate the substrate this command queried,
so suggesting they re-run it would be misleading):

  "No citation recommendations at threshold N=<threshold> for <gear>.
   Try --threshold 1 to see all external resources."
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    from canonicalize_url import canonicalize_url
except ImportError:  # pragma: no cover — package-relative fallback
    from .canonicalize_url import canonicalize_url  # type: ignore


# Excerpt length around a URL match in a citing chunk's content.
EXCERPT_MAX = 80

# Permissive http(s) URL regex; mirrors external_resource_sweep.URL_RE.
URL_RE = re.compile(r"https?://[^\s<>\"'\\)]+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public dataclass — consumed verbatim by Plan 04-03 (verified promotion)
# ---------------------------------------------------------------------------


@dataclass
class Recommendation:
    """Locked output shape for a single citation recommendation.

    Fields:
      canonical_url:               output of canonicalize_url for the resource
      resource_type:               "youtube" | "article" | "reddit-post" | "image" | "other"
      creator:                     str (may be "")
      title:                       str (may be "")
      independent_source_count:    distinct-source count compared against threshold
      citing_chunks:               list of {id, source, excerpt} dicts
      external_resource_chunk_id:  id of the external_resource chunk this rec is built from
    """

    canonical_url: str
    resource_type: str
    creator: str
    title: str
    independent_source_count: int
    citing_chunks: list = field(default_factory=list)
    external_resource_chunk_id: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _walk_strings(value: Any) -> Iterable[str]:
    """Yield every string anywhere in a nested dict/list structure.

    Mirrors the Plan 04-01 sweep helper of the same name. Used to find
    URL matches in arbitrary chunk content shapes.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_strings(v)


def _strip_trailing_punct(url: str) -> str:
    """Trim sentence-ending punctuation from a URL captured in prose."""
    return url.rstrip(".,;:!?)\"'")


def _truncate_excerpt(text: str, start: int, end: int) -> str:
    """Return an EXCERPT_MAX-bounded window around [start, end) with
    "..." truncation markers when the source string is longer.
    """
    text_len = len(text)
    if text_len <= EXCERPT_MAX:
        return text
    span = end - start
    if span >= EXCERPT_MAX:
        # The match itself is already too long — keep its head.
        snippet = text[start : start + EXCERPT_MAX]
        suffix = "..." if start + EXCERPT_MAX < text_len else ""
        return snippet + suffix
    # Center a window of EXCERPT_MAX chars around the match.
    pad = (EXCERPT_MAX - span) // 2
    w_start = max(0, start - pad)
    w_end = min(text_len, w_start + EXCERPT_MAX)
    # If we hit the right edge, shift the start left.
    if w_end - w_start < EXCERPT_MAX:
        w_start = max(0, w_end - EXCERPT_MAX)
    snippet = text[w_start:w_end]
    prefix = "..." if w_start > 0 else ""
    suffix = "..." if w_end < text_len else ""
    return prefix + snippet + suffix


def _excerpt_for_url(chunk: dict, canonical_url: str) -> str:
    """Find the first URL match in chunk.content whose canonical form
    equals `canonical_url`; return up to EXCERPT_MAX chars surrounding
    it. Fallback: first EXCERPT_MAX chars of any content string.
    """
    content = chunk.get("content")
    for s in _walk_strings(content):
        if not isinstance(s, str):
            continue
        for m in URL_RE.finditer(s):
            raw = _strip_trailing_punct(m.group(0))
            try:
                if canonicalize_url(raw) == canonical_url:
                    return _truncate_excerpt(s, m.start(), m.start() + len(raw))
            except Exception:
                continue
    # Fallback: first non-empty content string, truncated.
    for s in _walk_strings(content):
        if isinstance(s, str) and s.strip():
            if len(s) <= EXCERPT_MAX:
                return s
            return s[:EXCERPT_MAX] + "..."
    return ""


def _read_chunks(chunks_path: Path) -> list[dict]:
    """Read a chunks.jsonl file; skip malformed lines silently.

    Mirrors external_resource_sweep's defensive read — a malformed
    line in chunks.jsonl must not crash the aggregator (trust
    boundary T-04-07).
    """
    chunks: list[dict] = []
    if not chunks_path.exists():
        return chunks
    with chunks_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                chunks.append(obj)
    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def aggregate_citations(
    chunks_path: Path,
    threshold: int = 2,
    filter_url: Optional[str] = None,
) -> list[Recommendation]:
    """Group external_resource chunks by canonical URL and surface every
    URL with at least ``threshold`` DISTINCT citing-chunk sources.

    Args:
      chunks_path:  path to a per-gear chunks.jsonl
      threshold:    int >= 1; default 2 (CITATION-02)
      filter_url:   if non-empty, restrict to recommendations whose
                    canonical_url matches canonicalize_url(filter_url).

    Returns:
      list[Recommendation] sorted by (-independent_source_count, canonical_url).

    Raises:
      ValueError if threshold < 1.
    """
    if threshold < 1:
        raise ValueError(f"threshold must be >= 1 (got {threshold})")

    chunks = _read_chunks(chunks_path)
    by_id: dict[str, dict] = {}
    for c in chunks:
        cid = c.get("id")
        if isinstance(cid, str) and cid:
            by_id[cid] = c

    # Resolve filter_url to its canonical form (T-04-07: a non-http(s)
    # filter_url canonicalizes to "" and short-circuits the result set).
    filter_canonical: Optional[str] = None
    if filter_url is not None:
        canon = canonicalize_url(filter_url)
        if not canon:
            return []
        filter_canonical = canon

    recommendations: list[Recommendation] = []

    for chunk in chunks:
        if chunk.get("type") != "external_resource":
            continue
        content = chunk.get("content") or {}
        raw_url = content.get("url") or ""
        canonical = canonicalize_url(raw_url) if raw_url else ""
        if not canonical:
            continue
        if filter_canonical is not None and canonical != filter_canonical:
            continue

        citing_ids = content.get("citing_chunk_ids") or []
        if not isinstance(citing_ids, list):
            continue

        sources: set[str] = set()
        citing_records: list[dict] = []
        for cid in citing_ids:
            if not isinstance(cid, str):
                continue
            citing = by_id.get(cid)
            if citing is None:
                continue
            # An external_resource chunk is a citation TARGET, not a
            # SOURCE — do not let it cast a vote.
            if citing.get("type") == "external_resource":
                continue
            src = citing.get("source")
            if not isinstance(src, str) or not src:
                continue
            sources.add(src)
            citing_records.append(
                {
                    "id": cid,
                    "source": src,
                    "excerpt": _excerpt_for_url(citing, canonical),
                }
            )

        independent_source_count = len(sources)
        if independent_source_count < threshold:
            continue

        # Sort citing_records by (source, id) for deterministic output.
        citing_records.sort(key=lambda r: (r.get("source", ""), r.get("id", "")))

        recommendations.append(
            Recommendation(
                canonical_url=canonical,
                resource_type=str(content.get("resource_type") or "other"),
                creator=str(content.get("creator") or ""),
                title=str(content.get("title") or ""),
                independent_source_count=independent_source_count,
                citing_chunks=citing_records,
                external_resource_chunk_id=str(chunk.get("id") or ""),
            )
        )

    recommendations.sort(key=lambda r: (-r.independent_source_count, r.canonical_url))
    return recommendations


def format_recommendations_markdown(
    recommendations: list[Recommendation],
    gear: str,
    threshold: int,
) -> str:
    """Render `recommendations` as a markdown block for terminal display.

    Empty-result wording is LOCKED at v2.0 per W3 — it does NOT suggest
    re-running ``/patchbay:research <gear>``, because the user has just
    run that command to produce the substrate this query consumed.
    """
    if not recommendations:
        return (
            f"No citation recommendations at threshold N={threshold} for {gear}. "
            f"Try --threshold 1 to see all external resources."
        )

    # Defensive re-sort: aggregate_citations already sorts by
    # (-source_count, canonical_url), but the formatter is a public
    # entry point and may be called with hand-built Recommendation
    # lists (Plan 04-03's verified-promotion preview, tests, etc.). A
    # 3-source recommendation MUST appear before a 2-source one
    # regardless of input order — that ordering is the load-bearing
    # display rule (see test_format_orders_recommendations_by_source_count_desc).
    ordered = sorted(
        recommendations,
        key=lambda r: (-r.independent_source_count, r.canonical_url),
    )

    lines: list[str] = []
    lines.append(f"# Citation recommendations for {gear} (threshold N={threshold})")
    lines.append("")
    lines.append(
        f"Showing {len(ordered)} resource(s) cited by >= {threshold} "
        f"independent sources."
    )
    lines.append("")

    for idx, rec in enumerate(ordered, start=1):
        citing_n = len(rec.citing_chunks)
        sources_n = rec.independent_source_count
        lines.append(
            f"## {idx}. {rec.canonical_url} — referenced {citing_n} times "
            f"across {sources_n} sources"
        )
        lines.append(f"- type: {rec.resource_type}")
        if rec.creator:
            lines.append(f"- creator: {rec.creator}")
        if rec.title:
            lines.append(f"- title: {rec.title}")
        lines.append("- citing chunks:")
        for cc in rec.citing_chunks:
            cid = cc.get("id", "")
            src = cc.get("source", "")
            excerpt = cc.get("excerpt", "")
            # Replace any embedded newlines in the excerpt for clean
            # single-line markdown rendering.
            excerpt_oneline = excerpt.replace("\n", " ").replace("\r", " ").strip()
            lines.append(f"  - [{src}] {cid} — \"{excerpt_oneline}\"")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_threshold_from_env() -> int:
    """Return the env-var-derived default threshold (positive int) or 2."""
    raw = os.environ.get("PATCHBAY_CITATION_THRESHOLD", "")
    if raw.isdigit():
        n = int(raw)
        if n >= 1:
            return n
    return 2


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="citations.py",
        description=(
            "Surface external resources cited by >= N independent sources "
            "across a gear's chunks.jsonl (CITATION-02)."
        ),
    )
    parser.add_argument(
        "chunks_path",
        type=Path,
        help="Path to the per-gear chunks.jsonl",
    )
    parser.add_argument(
        "--gear",
        required=True,
        help="Brand + item label shown in the output (e.g., 'Chase Bliss MOOD MkII')",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=_default_threshold_from_env(),
        help=(
            "Minimum number of DISTINCT citing-chunk sources required to surface "
            "a recommendation (default 2; PATCHBAY_CITATION_THRESHOLD env var "
            "overrides default; flag overrides env)."
        ),
    )
    parser.add_argument(
        "--filter-url",
        default=None,
        help="If set, restrict output to recommendations whose canonical URL matches.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON array of Recommendation dicts instead of markdown.",
    )

    ns = parser.parse_args(argv)

    try:
        recs = aggregate_citations(
            ns.chunks_path,
            threshold=ns.threshold,
            filter_url=ns.filter_url,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2  # parser.error exits — defensive return for type-checkers

    if ns.json:
        sys.stdout.write(
            json.dumps([asdict(r) for r in recs], ensure_ascii=False, indent=2)
        )
        sys.stdout.write("\n")
    else:
        sys.stdout.write(
            format_recommendations_markdown(
                recs, gear=ns.gear, threshold=ns.threshold
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
