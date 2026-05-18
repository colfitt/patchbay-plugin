"""verify_resource — mark a surfaced citation recommendation as verified.

Dispatches downstream ingestion via the existing url_router (Plan 03-01) and
stamps every produced chunk with trust='high'. CITATION-03 deliverable
(Plan 04-03, Phase 4 closing brick).

Flow:
  1. canonicalize_url(input URL) — reject non-http(s) up front (T-04-13).
  2. Locate the existing external_resource chunk whose content.url canonicalizes
     to the same form. If absent → return a structured error pointing the
     user at /patchbay:research --citations <gear>.
  3. route_url(canonical, registry) → source-class module (Plan 03-01).
  4. fetch_tier1(canonical). YouTube returns the needs_pipeline=True sentinel
     (source_classes/youtube.py L88-L101) — dispatch parse_to_chunks DIRECTLY
     with the sentinel; do NOT treat as a fetch failure.
  5. parse_to_chunks(result, gear_ctx) → new_chunks.
  6. promote_chunks_to_high_trust(new_chunks) → defense-in-depth: stamp the
     chunks BEFORE write_chunks. The write_chunks trust= parameter
     (Plan 04-03 addition) also stamps as a second line of defense.
  7. update_chunk_field(chunks_path, ext_id, "content.relevance", "verified", ...)
     and update_chunk_field(chunks_path, ext_id, "trust", "high", ...).
     Single-segment field_path "trust" sets the top-level key cleanly even
     when absent (write_chunk.py L309-L329 — parts[:-1] empty, parent-walk
     skipped, leaf assignment sets chunk["trust"] = "high").

Idempotency: re-running verify_resource for the same URL is safe.
  - canonical URL is unchanged.
  - external_resource trust/relevance overwritten with the same values
    (no-op effect via update_chunk_field's atomic rewrite).
  - Downstream ingestion DOES re-fetch — the user explicitly re-invoked
    --verify, so fresh data is the right behavior. Newly emitted chunks
    get trust=high.
  - chunks.jsonl grows monotonically; the Plan 04-01 post-write sweep
    handles dedup at the external_resource layer.

CLI surface (Plan 04-03):
  python3 verify_resource.py <chunks_path> --gear "<Brand Item>" --url <url> [--gear-root <path>]

Exit codes:
  0 — success.
  1 — fetch failure OR gear_root derivation failure (default --gear-root
      walks three parent levels from chunks.jsonl: chunks.jsonl → knowledge/
      → <Brand Item>/ → <gear_root>; W6 fix).
  2 — no external_resource chunk represents the URL; stderr suggests
      /patchbay:research --citations <gear>.

Threat-model dispositions (full register in 04-03-PLAN.md):
  - T-04-13 Tampering / argv --url: canonicalize_url rejects non-http(s)
    schemes; route_url + match_url further verify.
  - T-04-14 Elevation / trust=high: only verify_resource sets trust=high.
  - T-04-19 Tampering / injectable registry env var: importlib raises
    ImportError loudly on missing/bad module; surfaced to stderr.
  - T-04-20 Tampering / --gear-root traversal: write_chunks +
    update_chunk_field enforce _validate_path_containment (T-03-04 inherited).
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

# Make sibling modules importable when this file is run as a script.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

try:
    from canonicalize_url import canonicalize_url
except ImportError:  # pragma: no cover — package-relative fallback
    from .canonicalize_url import canonicalize_url  # type: ignore

try:
    from url_router import route_url
except ImportError:  # pragma: no cover
    from .url_router import route_url  # type: ignore

try:
    from write_chunk import write_chunks, update_chunk_field
except ImportError:  # pragma: no cover
    from .write_chunk import write_chunks, update_chunk_field  # type: ignore


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def promote_chunks_to_high_trust(chunks: List[dict]) -> List[dict]:
    """Return a NEW list where each chunk has chunk["trust"] = "high".

    Does NOT mutate the input list or its members (deepcopy each chunk).
    This is defense-in-depth alongside write_chunks(..., trust="high"): even
    if a future caller forgets to pass trust= to write_chunks, the chunks
    themselves are already stamped before the writer sees them.
    """
    out: List[dict] = []
    for chunk in chunks:
        new_chunk = copy.deepcopy(chunk)
        new_chunk["trust"] = "high"
        out.append(new_chunk)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_chunks(chunks_path: Path) -> List[dict]:
    """Defensive read of chunks.jsonl: skip malformed lines silently.

    Mirrors citations.py's defensive reader (trust boundary T-04-07-like:
    a malformed line must not crash the verify flow).
    """
    out: List[dict] = []
    if not chunks_path.exists():
        return out
    for line in chunks_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _find_external_resource_for(
    chunks: List[dict],
    canonical: str,
) -> Optional[dict]:
    """Return the external_resource chunk whose content.url canonicalizes to
    `canonical`, or None if no match.
    """
    for chunk in chunks:
        if chunk.get("type") != "external_resource":
            continue
        content = chunk.get("content") or {}
        raw_url = content.get("url") or ""
        if not isinstance(raw_url, str) or not raw_url:
            continue
        if canonicalize_url(raw_url) == canonical:
            return chunk
    return None


def _make_error(
    *,
    url: str,
    error: str,
) -> dict:
    return {
        "ok": False,
        "url": url,
        "chunks_added": 0,
        "external_resource_id": "",
        "error": error,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_resource(
    chunks_path,
    gear_ctx: dict,
    url: str,
    *,
    registry: list,
    mcp_tools: Optional[dict] = None,
    prompt_user=None,
) -> dict:
    """Mark the external_resource chunk for `url` as verified; re-ingest
    fresh chunks and stamp them with trust='high'.

    Args:
      chunks_path: Path or str — path to chunks.jsonl.
      gear_ctx:    {"gear_root": str|Path, "item": "Brand Item"}.
      url:         raw URL from user; canonicalized internally.
      registry:    list of source-class modules (typically source_classes.REGISTRY).
                   Injectable for tests + the CLI's env-var override.
      mcp_tools:   reserved for tier-2/tier-3 future use; passed-through context.
      prompt_user: reserved for future interactive choice; defaults to None.

    Returns:
      {"ok": bool,
       "url": canonical_url,
       "chunks_added": int,
       "external_resource_id": str,
       "error": Optional[str]}
    """
    chunks_path = Path(chunks_path)

    # Step A — canonicalize, reject non-http(s) (T-04-13).
    canonical = canonicalize_url(url)
    if not canonical:
        return _make_error(
            url="",
            error=f"URL not usable: {url!r}",
        )

    # Step B — locate the existing external_resource chunk.
    chunks = _read_chunks(chunks_path)
    ext_chunk = _find_external_resource_for(chunks, canonical)
    if ext_chunk is None:
        return _make_error(
            url=canonical,
            error=(
                f"No external_resource chunk found for {canonical!r}. "
                f"Run /patchbay:research --citations <gear> first to see what's "
                f"actually been referenced."
            ),
        )
    ext_id = str(ext_chunk.get("id") or "")
    if not ext_id:
        return _make_error(
            url=canonical,
            error=f"external_resource chunk for {canonical!r} has no id.",
        )

    # Step C — dispatch via url_router. Empty registry raises ValueError;
    # catch and surface as structured error (T-04-19 path).
    try:
        source_module = route_url(canonical, registry)
    except ValueError as exc:
        return _make_error(
            url=canonical,
            error=(
                f"No source class matched {canonical!r} and registry is empty: {exc}"
            ),
        )
    if source_module is None:
        return _make_error(
            url=canonical,
            error=f"No source class matched {canonical!r} and no generic fallback in registry.",
        )

    # Step D — fetch tier-1. YouTube's sentinel `needs_pipeline=True` is NOT
    # a failure: it means the SKILL driver should call parse_to_chunks
    # directly. Mirror that here.
    fetch_fn = getattr(source_module, "fetch_tier1", None)
    parse_fn = getattr(source_module, "parse_to_chunks", None)
    if not callable(fetch_fn) or not callable(parse_fn):
        return _make_error(
            url=canonical,
            error=(
                f"Source class {getattr(source_module, '__name__', '<anon>')!r} "
                f"missing fetch_tier1/parse_to_chunks callable."
            ),
        )

    try:
        fetch_result = fetch_fn(canonical)
    except Exception as exc:  # pragma: no cover — source class is responsible
        return _make_error(
            url=canonical,
            error=f"Fetch raised: {exc!r}",
        )

    if isinstance(fetch_result, dict):
        needs_pipeline = bool(fetch_result.get("needs_pipeline"))
        status = fetch_result.get("status", 0)
    else:
        needs_pipeline = False
        status = 0

    # YouTube sentinel: status==0 with needs_pipeline=True is the valid
    # "skip the static fetch, hand off to the multimodal pipeline" path.
    # Non-sentinel status >= 400 is a real fetch failure.
    if not needs_pipeline and isinstance(status, int) and status >= 400:
        return _make_error(
            url=canonical,
            error=f"Fetch failed: HTTP {status}",
        )

    # Step E — parse to chunks.
    try:
        new_chunks = parse_fn(fetch_result, gear_ctx)
    except Exception as exc:  # pragma: no cover — source class is responsible
        return _make_error(
            url=canonical,
            error=f"parse_to_chunks raised: {exc!r}",
        )
    if not isinstance(new_chunks, list):
        new_chunks = []

    # Step F — stamp trust=high (defense-in-depth) + append via write_chunks
    # which ALSO stamps trust=high through its Plan 04-03 keyword-only param.
    stamped = promote_chunks_to_high_trust(new_chunks)
    gear_root_value = gear_ctx.get("gear_root") if isinstance(gear_ctx, dict) else None
    gear_root_str: Optional[str] = (
        str(gear_root_value) if gear_root_value is not None else None
    )

    write_chunks(
        str(chunks_path),                 # path FIRST (positional) — deployed signature
        stamped,                          # chunks SECOND (positional)
        gear_root=gear_root_str,
        trust="high",                     # NEW keyword-only param (Plan 04-03)
    )

    # Step G — atomic update_chunk_field calls (dotted-string field_path).
    update_chunk_field(
        str(chunks_path),                 # path FIRST positional — deployed signature
        ext_id,                           # chunk_id SECOND
        "content.relevance",              # dotted-string field_path THIRD
        "verified",                       # new_value FOURTH
        gear_root=gear_root_str,
    )
    update_chunk_field(
        str(chunks_path),
        ext_id,
        "trust",                          # single-segment field_path — sets chunk["trust"]
        "high",
        gear_root=gear_root_str,
    )

    return {
        "ok": True,
        "url": canonical,
        "chunks_added": len(stamped),
        "external_resource_id": ext_id,
        "error": None,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_registry_for_cli() -> list:
    """Resolve the REGISTRY to use for CLI dispatch.

    If env PATCHBAY_VERIFY_REGISTRY_MODULE is set, importlib that dotted
    module path and return its REGISTRY (test-injectable). Otherwise import
    the real source_classes package and return source_classes.REGISTRY.

    Raises ImportError surfaced to the caller if the env-var override does
    not resolve (T-04-19).
    """
    override = os.environ.get("PATCHBAY_VERIFY_REGISTRY_MODULE", "").strip()
    if override:
        mod = importlib.import_module(override)
        registry = getattr(mod, "REGISTRY", None)
        if registry is None:
            raise ImportError(
                f"Module {override!r} has no REGISTRY attribute "
                f"(PATCHBAY_VERIFY_REGISTRY_MODULE override)."
            )
        return registry
    # Real source-classes registry.
    try:
        import source_classes  # type: ignore
    except ImportError:  # pragma: no cover — package-relative fallback
        from .. import source_classes  # type: ignore
    return getattr(source_classes, "REGISTRY")


def _derive_gear_root(chunks_path: Path) -> Optional[Path]:
    """W6 fix: chunks.jsonl → knowledge/ → <Brand Item>/ → <gear_root>.

    Three parent levels, NOT two. Returns None when the derivation does not
    resolve to an existing directory; the CLI surfaces a clear error in
    that case.
    """
    try:
        derived = Path(chunks_path).resolve().parent.parent.parent
    except (OSError, ValueError):
        return None
    if derived.is_dir():
        return derived
    return None


def _main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_resource.py",
        description=(
            "Mark a surfaced citation recommendation as verified; dispatch "
            "downstream ingestion and promote resulting chunks to trust=high "
            "(CITATION-03)."
        ),
    )
    parser.add_argument(
        "chunks_path",
        type=Path,
        help="Path to the per-gear chunks.jsonl.",
    )
    parser.add_argument(
        "--gear",
        required=True,
        help="Brand + item label (used to populate gear_ctx['item']).",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL to verify (any variant; canonicalized internally).",
    )
    parser.add_argument(
        "--gear-root",
        default=None,
        type=Path,
        help=(
            "gear_root directory. When omitted, derived from chunks_path "
            "(three parent levels up: chunks.jsonl -> knowledge -> <Brand Item> "
            "-> <gear_root>)."
        ),
    )

    ns = parser.parse_args(argv)

    if ns.gear_root is None:
        derived = _derive_gear_root(ns.chunks_path)
        if derived is None:
            sys.stderr.write(
                f"Could not derive gear_root from {ns.chunks_path}. "
                f"Pass --gear-root explicitly.\n"
            )
            return 1
        gear_root = derived
    else:
        gear_root = ns.gear_root.resolve()

    gear_ctx = {"gear_root": str(gear_root), "item": ns.gear}

    try:
        registry = _load_registry_for_cli()
    except ImportError as exc:
        sys.stderr.write(f"Failed to load registry: {exc}\n")
        return 1

    result = verify_resource(
        ns.chunks_path,
        gear_ctx,
        ns.url,
        registry=registry,
    )

    if result.get("ok"):
        sys.stdout.write(
            f"Verified {result['url']}: added {result['chunks_added']} chunks "
            f"at trust=high; external_resource {result['external_resource_id']} "
            f"marked relevance=verified.\n"
        )
        return 0

    err = result.get("error") or "verify failed"
    sys.stderr.write(err + "\n")
    if "No external_resource chunk" in err:
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
