"""Interactive review loop for `/patchbay:research --review-failures`.

Plan 05 of `/patchbay:research`. The user runs `--review-failures` after a
fresh tier-1 research run leaves failures.log entries; this module walks
each unresolved entry, prompts for one of four choices (tier-2, tier-3,
paste, skip), and dispatches accordingly.

PUBLIC API
==========

  load_failures(failures_log_path) -> list[dict]
      Parse failures.log; filter out resolution records and any failure
      with a later resolution record for the same URL. Skips malformed
      lines with a printed warning. Never raises.

  append_resolution(failures_log_path, url, tier_used, outcome,
                    chunks_written) -> None
      Append a single JSON line with `type: "resolution"` plus the schema
      from the plan's `<interfaces>` block. Append-only — the original
      failure line is preserved (RESEARCH-04 audit trail).

  review_failures(failures_log_path, chunks_jsonl_path, gear_ctx,
                  prompt_user, mcp_tools) -> dict
      The orchestrator. `prompt_user` and `mcp_tools` are injected for
      testability and so the SKILL driver can wire them to the real MCP
      surface (or a CLI-prompt loop). Returns
        {processed, escalated, skipped, extension_missing}
      Caller decides what to print at the end.

NO AUTO-FALLBACK (T-03-33)
==========================

  This module dispatches to EXACTLY one escalation path per failure, chosen
  by the user. On tier-2 precheck failure OR fetch error, the loop appends
  a resolution and MOVES ON to the next failure — it NEVER calls fetch_tier3
  or any other tier automatically. This invariant is covered by
  `test_review_choice_tier2_extension_missing_does_not_fallback` and
  `test_no_auto_fallback_after_tier2_fetch_failure`.

SECURITY (T-03-27 — malformed-line crash)
=========================================

  `load_failures` wraps each `json.loads` in try/except; a malformed line
  emits a warning and is skipped. The loop continues with the surrounding
  valid entries; never raises to the caller.

SECURITY (T-03-30 — pasted body)
================================

  Pasted bodies (tier 0) are opaque strings passed verbatim to the matched
  source class's `parse_to_chunks`. The same parser hardening that ran for
  tier-1 ingest (BeautifulSoup html.parser, JSON encoder via write_chunks,
  URL scheme re-validation on extracted external links) applies — the tier
  number only changes the `tier_used` field on the emitted chunks.

SECURITY (T-03-32 — bounded retry on bad user input)
====================================================

  Unknown choice strings re-prompt up to 3 times, then default to "skip"
  with a printed warning. Prevents an infinite loop on a buggy / scripted
  prompt_user.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

# Make sibling scripts importable regardless of cwd.
HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))

import tier2_chrome  # noqa: E402
import tier3_vision  # noqa: E402
from url_router import route_url  # noqa: E402
from write_chunk import write_chunks  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CHOICES = frozenset({"tier-2", "tier-3", "paste", "skip"})
MAX_REPROMPTS = 3

# Outcome enum values (single source of truth for tests + docs).
OUTCOME_SUCCESS = "success"
OUTCOME_USER_SKIPPED = "user-skipped"
OUTCOME_EXTENSION_MISSING = "extension-missing"
OUTCOME_TIER_ERROR = "tier-error"


# ---------------------------------------------------------------------------
# load_failures
# ---------------------------------------------------------------------------

def load_failures(failures_log_path: str) -> List[dict]:
    """Return unresolved failure entries from `failures_log_path`.

    Implementation:
      1. Read each line, json-parse. Malformed lines warn + skip.
      2. Split records into resolutions (`type == "resolution"`) and
         failures (everything else with a `url` key).
      3. Filter out failures whose URL appears in any resolution record
         that comes LATER in the file.

    Order is preserved for the returned failures — first failure in the
    file is first in the returned list.
    """
    path = Path(failures_log_path)
    if not path.exists():
        return []

    records: List[dict] = []
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    for lineno, line in enumerate(raw_lines, start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                f"[review_failures] warning: skipping malformed line {lineno} "
                f"in {path}: {exc}"
            )
            continue
        if not isinstance(obj, dict):
            print(
                f"[review_failures] warning: skipping non-dict line {lineno} "
                f"in {path}."
            )
            continue
        records.append(obj)

    resolutions = [r for r in records if r.get("type") == "resolution"]
    resolved_urls = {r.get("url") for r in resolutions if r.get("url")}

    return [
        r
        for r in records
        if r.get("type") != "resolution"
        and r.get("url") is not None
        and r.get("url") not in resolved_urls
    ]


# ---------------------------------------------------------------------------
# append_resolution
# ---------------------------------------------------------------------------

def append_resolution(
    failures_log_path: str,
    url: str,
    tier_used: Optional[int],
    outcome: str,
    chunks_written: int,
) -> None:
    """Append one JSONL line marking `url` resolved. Preserves append-only
    invariant — the original failure line is NEVER rewritten."""
    record = {
        "type": "resolution",
        "url": url,
        "resolved_at": datetime.utcnow().isoformat() + "Z",
        "tier_used": tier_used,
        "outcome": outcome,
        "chunks_written": chunks_written,
    }
    path = Path(failures_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # `json.dumps` — never raw concat (T-03-03 inherited).
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# review_failures (the orchestrator)
# ---------------------------------------------------------------------------

def review_failures(
    failures_log_path: str,
    chunks_jsonl_path: str,
    gear_ctx: dict,
    prompt_user: Callable[[Any], str],
    mcp_tools: Mapping[str, Callable],
    gear_root: Optional[str] = None,
) -> Dict[str, int]:
    """Walk unresolved failures and dispatch each one per user choice.

    `prompt_user(entry_or_str) -> str`:
        - When called with a failure dict: returns one of
          `"tier-2" | "tier-3" | "paste" | "skip"`. Unknown values re-prompt
          up to MAX_REPROMPTS times, then default to `"skip"`.
        - When called with a string sentinel (during the paste choice):
          returns the user's pasted DOM body verbatim.

    `mcp_tools` is a dict of injected callables exposing the MCP surface
    (list_connected_browsers, select_browser, tabs_context_mcp,
    browser_batch, get_page_text, request_access, screenshot). Tests pass
    stubs; the SKILL driver passes the real `mcp__*` tool references.

    Returns counts: processed, escalated, skipped, extension_missing.
    """
    entries = load_failures(failures_log_path)

    counts = {
        "processed": 0,
        "escalated": 0,
        "skipped": 0,
        "extension_missing": 0,
    }

    # Get REGISTRY lazily, and ensure all known source-class modules are
    # imported so REGISTRY is fully populated. After test-cycle reloads of
    # `source_classes` (which reset `REGISTRY` to []) the cached source-class
    # submodules in `sys.modules` no longer appear in REGISTRY — re-importing
    # is a no-op against the cached module. We detect that case and reload
    # the submodules so their self-registration tail re-runs against the
    # fresh list. Self-registration is idempotent (`if _self not in REGISTRY`).
    import importlib as _importlib  # noqa: WPS433
    import sys as _sys  # noqa: WPS433
    import source_classes  # noqa: WPS433
    for _modname in ("reddit", "equipboard", "youtube"):
        _full = f"source_classes.{_modname}"
        try:
            mod = _importlib.import_module(_full)
        except ImportError:  # pragma: no cover — optional in custom layouts
            continue
        if mod not in source_classes.REGISTRY:
            _importlib.reload(mod)
    REGISTRY = source_classes.REGISTRY

    for entry in entries:
        counts["processed"] += 1
        url = entry.get("url")
        _print_entry_summary(entry)

        choice = _resolve_choice(prompt_user, entry)

        if choice == "skip":
            append_resolution(
                failures_log_path,
                url=url,
                tier_used=None,
                outcome=OUTCOME_USER_SKIPPED,
                chunks_written=0,
            )
            counts["skipped"] += 1
            continue

        # Route the URL to a source class — same router as tier-1.
        source_class = route_url(url, REGISTRY)

        if choice == "tier-2":
            # Precheck FIRST. If it fails, append extension-missing AND
            # move on. NEVER auto-fall-through to tier 3 (T-03-33).
            if not tier2_chrome.precheck_chrome_extension(mcp_tools):
                append_resolution(
                    failures_log_path,
                    url=url,
                    tier_used=2,
                    outcome=OUTCOME_EXTENSION_MISSING,
                    chunks_written=0,
                )
                counts["extension_missing"] += 1
                continue

            try:
                fetch_result = tier2_chrome.fetch_tier2(url, mcp_tools)
            except Exception as exc:  # noqa: BLE001 — surface as resolution
                print(
                    f"[review_failures] tier-2 fetch raised {type(exc).__name__}: "
                    f"{exc}. NOT falling through to tier 3."
                )
                append_resolution(
                    failures_log_path,
                    url=url,
                    tier_used=2,
                    outcome=OUTCOME_TIER_ERROR,
                    chunks_written=0,
                )
                continue

            n = _parse_and_write(
                fetch_result, gear_ctx, source_class,
                chunks_jsonl_path, gear_root,
            )
            append_resolution(
                failures_log_path,
                url=url,
                tier_used=2,
                outcome=OUTCOME_SUCCESS,
                chunks_written=n,
            )
            counts["escalated"] += 1
            continue

        if choice == "tier-3":
            try:
                fetch_result = tier3_vision.fetch_tier3(
                    url, mcp_tools, prompt_user
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[review_failures] tier-3 fetch raised "
                    f"{type(exc).__name__}: {exc}. NOT falling through."
                )
                append_resolution(
                    failures_log_path,
                    url=url,
                    tier_used=3,
                    outcome=OUTCOME_TIER_ERROR,
                    chunks_written=0,
                )
                continue

            n = _parse_and_write(
                fetch_result, gear_ctx, source_class,
                chunks_jsonl_path, gear_root,
            )
            append_resolution(
                failures_log_path,
                url=url,
                tier_used=3,
                outcome=OUTCOME_SUCCESS,
                chunks_written=n,
            )
            counts["escalated"] += 1
            continue

        if choice == "paste":
            # Prompt with a string sentinel so the user's prompt_user shim
            # can distinguish action-selection from paste-body collection.
            pasted_body = prompt_user(
                f"Paste the DOM text for {url} (end with EOF / Ctrl-D):"
            )
            if not isinstance(pasted_body, str):
                pasted_body = str(pasted_body or "")

            fetch_result = {
                "status": 200,
                "body": pasted_body,
                "json": None,
                "url_attempted": url,
                "headers": {},
                "elapsed_ms": 0,
                "exc": None,
                "tier": 0,
            }
            try:
                n = _parse_and_write(
                    fetch_result, gear_ctx, source_class,
                    chunks_jsonl_path, gear_root,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[review_failures] paste parse raised "
                    f"{type(exc).__name__}: {exc}."
                )
                append_resolution(
                    failures_log_path,
                    url=url,
                    tier_used=0,
                    outcome=OUTCOME_TIER_ERROR,
                    chunks_written=0,
                )
                continue
            append_resolution(
                failures_log_path,
                url=url,
                tier_used=0,
                outcome=OUTCOME_SUCCESS,
                chunks_written=n,
            )
            counts["escalated"] += 1
            continue

    return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_entry_summary(entry: dict) -> None:
    """One-line summary per the plan's behavior: url, reason, http_status,
    suggested_escalation."""
    print(
        f"[review_failures] {entry.get('url')}  "
        f"reason={entry.get('reason')!r}  "
        f"http_status={entry.get('http_status')!r}  "
        f"suggested_escalation={entry.get('suggested_escalation')!r}"
    )


def _resolve_choice(
    prompt_user: Callable[[Any], str], entry: dict
) -> str:
    """Call `prompt_user(entry)`, validate against VALID_CHOICES, re-prompt
    up to MAX_REPROMPTS times, then default to 'skip' on persistent
    invalid input (T-03-32)."""
    for attempt in range(MAX_REPROMPTS + 1):
        choice = prompt_user(entry)
        if isinstance(choice, str):
            choice_norm = choice.strip().lower()
        else:
            choice_norm = ""
        if choice_norm in VALID_CHOICES:
            return choice_norm
        print(
            f"[review_failures] invalid choice {choice!r}; expected one of "
            f"{sorted(VALID_CHOICES)}. attempt={attempt + 1}/{MAX_REPROMPTS + 1}"
        )
    print(
        "[review_failures] defaulting to 'skip' after exhausting re-prompts."
    )
    return "skip"


def _parse_and_write(
    fetch_result: dict,
    gear_ctx: dict,
    source_class,
    chunks_jsonl_path: str,
    gear_root: Optional[str],
) -> int:
    """Run the source class's parse_to_chunks and write the result.

    Returns the number of chunks written. Also forces `tier_used` on every
    chunk to mirror `fetch_result["tier"]` if a parser hardcodes `tier_used: 1`
    (Plan 04 YouTube is an example) — the user-driven escalation tier MUST
    be reflected in the persisted chunks, NOT silently downgraded to tier 1.
    """
    tier = fetch_result.get("tier", 1)
    chunks = source_class.parse_to_chunks(fetch_result, gear_ctx)

    # Defensive: stamp `tier_used` to match `fetch_result["tier"]` so a
    # parser that hardcodes tier_used=1 (e.g., the youtube class today)
    # still reflects the actual escalation in chunks.jsonl. Plan 03 and
    # Plan 02 already honor fetch_result["tier"] so this is a no-op for
    # those parsers.
    for chunk in chunks:
        chunk["tier_used"] = tier

    if not chunks:
        return 0

    result = write_chunks(
        chunks_jsonl_path, chunks, gear_root=gear_root
    )
    return result.get("written", len(chunks))
