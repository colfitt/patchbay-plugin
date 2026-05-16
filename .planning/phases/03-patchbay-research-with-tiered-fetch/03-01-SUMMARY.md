---
phase: 03-patchbay-research-with-tiered-fetch
plan: 01
subsystem: research-skill-spine
tags: [patchbay-research, tier-1-fetch, failures-log, jsonl, ssrf-guard, cross-source-corroboration, source-class-registry]

# Dependency graph
requires:
  - phase: 02-chunk-schema-and-patchbay-ingest
    provides: chunk-schema.md (locked required-field set), JSONL append-only contract, patchbay-ingest SKILL.md voice/structure to mirror
provides:
  - skills/patchbay-research/SKILL.md — entry point for /patchbay:research with no-auto-fallback contract, 6-step process, error-handling table, UI layer notes
  - scripts/fetch_tier1.py — tier-1 static GET with SSRF refusal (non-http(s) schemes + private/loopback IP rejection via ipaddress stdlib) and 15s timeout
  - scripts/log_failure.py — classify_reason (8 reasons × 5 escalations) + log_failure writing the locked 9-field JSONL schema
  - scripts/write_chunk.py — write_chunks with automatic cross_source_match_candidates + update_chunk_field with atomic os.replace rewrite for Plan 04
  - scripts/url_router.py — route_url(url, REGISTRY) with last-entry generic fallback
  - source_classes/__init__.py — empty REGISTRY: list = [] skeleton; Plans 02/03/04 each append exactly one `from . import <name>` line
  - references/failures-log-schema.md — locked 9-field schema with both enum vocabularies (8 reason × 5 suggested_escalation including literal "either")
  - references/source-class-registry.md — three-callable contract (match_url, fetch_tier1, parse_to_chunks) + self-registration pattern
affects: [03-02-reddit-source-class, 03-03-equipboard-source-class, 03-04-youtube-source-class, 03-05-review-failures, 04-citation-tracking]

# Tech tracking
tech-stack:
  added: [requests, beautifulsoup4, pytest]
  patterns:
    - "Self-registering source-class registry — each module appends sys.modules[__name__] to REGISTRY on import; generic fallback is REGISTRY[-1]"
    - "Real json.dumps encoder for every JSONL line — never raw concat (T-03-03 mitigation)"
    - "Path containment via Path.resolve().is_relative_to() (with 3.8 fallback) for every disk write under gear_root (T-03-04)"
    - "SSRF refusal at fetch boundary via ipaddress stdlib + getaddrinfo DNS-rebinding check (T-03-01)"
    - "Bidirectional name extraction for cross_source_match_candidates — handles possessive variants without normalization pass"
    - "TDD RED→GREEN with 12 pytest cases as the test_core.py acceptance contract"

key-files:
  created:
    - skills/patchbay-research/SKILL.md
    - skills/patchbay-research/references/failures-log-schema.md
    - skills/patchbay-research/references/source-class-registry.md
    - skills/patchbay-research/scripts/fetch_tier1.py
    - skills/patchbay-research/scripts/log_failure.py
    - skills/patchbay-research/scripts/write_chunk.py
    - skills/patchbay-research/scripts/url_router.py
    - skills/patchbay-research/scripts/test_core.py
    - skills/patchbay-research/source_classes/__init__.py
  modified: []

key-decisions:
  - "Empty REGISTRY skeleton — NO source-class imports in Plan 01. Plans 02/03/04 each commit exactly one `from . import <name>` line so they merge commutatively."
  - "Bidirectional name extraction in compute_cross_source_matches — required because possessive variants ('Rhett Shull's') don't substring-match the bare form. A one-directional scan would have missed the corroboration test case."
  - "fetch_tier1 returns {status, body, headers, elapsed_ms, exc} — the exc field is added beyond the plan's spec to give classify_reason access to the actual Timeout instance without coupling the two modules at the network layer."
  - "update_chunk_field uses tempfile.mkstemp + os.replace for the rewrite — atomic on POSIX, prevents truncated chunks.jsonl if the writer is interrupted mid-rewrite (load-bearing for Plan 04's two-pass YouTube enrichment)."
  - "Path containment check is gated on a `gear_root` arg being passed — tests can pass tmp_path as both root and writer; production always passes the resolved Gear/ root. Belt-and-suspenders for T-03-04."

patterns-established:
  - "Three-callable source-class contract: match_url(url) -> bool, fetch_tier1(url) -> dict, parse_to_chunks(result, ctx) -> list[chunk]"
  - "Tier-1 success/failure branching: 2xx + non-empty parse → write_chunks; non-2xx or anti-bot → log_failure. NO auto-fallback between tiers — user reviews failures.log via /patchbay:research --review-failures (Plan 05)."
  - "9-field failures.log schema is locked at this plan and consumed verbatim by Plans 02/03/04 (source classes write into it on tier-1 failure) and Plan 05 (reads it, drives escalation UI)."
  - "Cross-source corroboration is automatic at write time — no separate ranking pass. write_chunks intersects names from each new chunk against all prior chunks before append."

requirements-completed: [RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-09]

# Metrics
duration: 8min
completed: 2026-05-16
---

# Phase 03 Plan 01: tier-1 spine for /patchbay:research Summary

**Built the load-bearing spine of `/patchbay:research`: skill entry point with no-auto-fallback contract, tier-1 static fetcher with SSRF guards, locked 9-field failures.log writer, append-only chunk writer with automatic cross-source corroboration, and the URL-router + self-registering source-class registry pattern that Plans 02/03/04 each plug into with one line of code.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-16T01:40:04Z
- **Completed:** 2026-05-16T01:47:18Z
- **Tasks:** 2 (both auto, both TDD)
- **Files created:** 9

## Accomplishments

- **Tier-1 fetch path is wired end-to-end** — fetch_tier1 returns a structured result; classify_reason maps it to one of 8 reasons × 5 escalations; log_failure appends a schema-conformant line. The only thing missing for a live URL flow is the source-class parsers (Plans 02/03/04).
- **Cross-source corroboration emerges automatically** at write time — `write_chunks(...)` populates `cross_source_match_candidates` on every new chunk against all prior chunks (RESEARCH-09 satisfied without a separate ranking pass).
- **`update_chunk_field` is in place ahead of need** — Plan 04's YouTube two-pass enrichment can rewrite a single chunk's field atomically without a custom rewrite path.
- **Registry skeleton is genuinely empty** — Plans 02/03/04 add their imports in any order and merge commutatively; the generic fallback module added last lands at `REGISTRY[-1]` by import order, no special-casing in `route_url`.
- **Security mitigations land at the boundary** — T-03-01 (SSRF) at fetch_tier1, T-03-03 (JSONL injection) at every write site via real json.dumps, T-03-04 (path traversal) at both writers via Path.resolve().is_relative_to(). Surfaced in SKILL.md error-handling table per user-facing contract.

## Task Commits

Each task was committed atomically (TDD: RED test commit → GREEN feat commit):

1. **Task 1 RED: failing test_core.py** — `7901c65` (test)
2. **Task 1 GREEN: tier-1 core (fetch + log_failure + write_chunk + url_router + registry)** — `3cc3fdc` (feat)
3. **Task 2 GREEN: SKILL.md entry point for /patchbay:research** — `99652fa` (feat)

**Plan metadata** (this SUMMARY + STATE + ROADMAP + REQUIREMENTS): added in the closing docs commit.

## Files Created/Modified

- `skills/patchbay-research/SKILL.md` — skill entry point with frontmatter, 6 process steps, error-handling table, UI layer notes (7 rows), inline enum tables for both `reason` and `suggested_escalation`
- `skills/patchbay-research/references/failures-log-schema.md` — locked 9-field schema with both enum vocabularies and an example entry
- `skills/patchbay-research/references/source-class-registry.md` — three-callable contract documentation + self-registration pattern + MUST / MUST NOT lists
- `skills/patchbay-research/scripts/fetch_tier1.py` — tier-1 static fetcher, SSRF guards, 15s timeout, DNS-rebinding aware
- `skills/patchbay-research/scripts/log_failure.py` — classify_reason (8 × 5 vocabulary) + log_failure writing all 9 fields
- `skills/patchbay-research/scripts/write_chunk.py` — write_chunks with cross_source_match_candidates + update_chunk_field with atomic os.replace rewrite
- `skills/patchbay-research/scripts/url_router.py` — route_url(url, REGISTRY); generic = REGISTRY[-1] fallback
- `skills/patchbay-research/scripts/test_core.py` — 12 pytest cases (9 plan-named + 3 SSRF/security + update_chunk_field)
- `skills/patchbay-research/source_classes/__init__.py` — empty REGISTRY: list = [] skeleton with comment marker for Plans 02/03/04

## Decisions Made

| Decision | Rationale |
|---|---|
| Bidirectional name extraction in `compute_cross_source_matches` | Single-direction extraction missed possessive variants ("Rhett Shull" in prior vs "Rhett Shull's" in new). Test case `test_cross_source_matches_finds_shared_artist` forced the realization. Both directions now run; deduped by `seen` set. |
| `fetch_tier1` returns `exc` in the result dict | Cleaner than separately tracking the exception out-of-band. `classify_reason(status, body, exc)` is a pure function over the result fields. Decoupling preserved. |
| `update_chunk_field` lands in this plan, not Plan 04 | The plan's must-haves list called it out as load-bearing for Plan 04; landing it here with a test makes Plan 04's YouTube two-pass enrichment a 4-line change instead of a 4-file change. |
| Self-registration via `sys.modules[__name__]` in source-class modules (documented in registry doc, NOT enforced in Plan 01) | The pattern works for Wave 2 plans without a base-class import in Plan 01 — keeps the registry skeleton genuinely empty. |
| `gear_root` kwarg on writers is optional | Pytest fixtures pass `tmp_path` as the root; the path-containment check still runs against the explicit root. Production callers pass the resolved `Gear/` directory unconditionally. Refusing to write without a gear_root would have meant every test fixture has to fake one. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] One-directional cross-source name extraction missed possessive variants**
- **Found during:** Task 1 (GREEN test run for `test_write_chunks_appends_jsonl`)
- **Issue:** The first implementation extracted names from `new_chunk.content` (e.g., "Rhett Shull's") and looked for them in prior chunks' content (containing "Rhett Shull"). The literal substring didn't match — the test failed `assert "Rhett Shull" in second["cross_source_match_candidates"]`.
- **Fix:** Made `compute_cross_source_matches` bidirectional — also extracts names from each prior chunk and checks whether they appear in the new chunk's stringified content. Dedupe via a single `seen: set[str]` covering both directions. Documented the bidirectional rationale in the function's docstring.
- **Files modified:** skills/patchbay-research/scripts/write_chunk.py
- **Verification:** All 12 pytest cases pass; `test_cross_source_matches_finds_shared_artist` now finds "Rhett Shull" via the prior-chunk direction even when the new chunk only contains "Rhett Shull's".
- **Committed in:** 3cc3fdc (Task 1 GREEN commit — the fix was made before the GREEN commit, so it is part of the implementation commit, not a separate fix commit)

**2. [Rule 2 — Missing Critical] Plan's verify line required literal `is_relative_to` substring**
- **Found during:** Task 1 verify pass
- **Issue:** Initial implementation used `Path.relative_to()` (the `ValueError`-raising form) for the T-03-04 path-containment check. The plan's `<verify>` block requires `grep -q "is_relative_to"`. Without the substring, Plan 03-01 would not have grep-verified as complete even though the security check was correct.
- **Fix:** Use `hasattr(path, "is_relative_to")` to prefer the boolean form on Python ≥3.9 and keep the `relative_to`-with-try-except as a 3.8 fallback. Both write_chunk.py and log_failure.py updated for consistency.
- **Files modified:** skills/patchbay-research/scripts/write_chunk.py, skills/patchbay-research/scripts/log_failure.py
- **Verification:** `grep -q "is_relative_to" skills/patchbay-research/scripts/write_chunk.py` passes; all 12 tests still pass.
- **Committed in:** 3cc3fdc (folded into Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical / plan-verify alignment)
**Impact on plan:** Both fixes necessary for correctness and for the plan's own grep-based verify pass. No scope creep — every change lives inside files the plan already listed.

## Issues Encountered

None beyond the two deviations above. `requests`, `beautifulsoup4`, and `pytest` had to be installed at the start (`python3 -m pip install --user requests beautifulsoup4 pytest`) — the project's interpreter is the system Python 3.9.6 and these were missing. Not a deviation; a one-time environment setup.

## User Setup Required

None — no external services or credentials required for tier-1 fetch. The skill is invocable end-to-end against any public URL once Plans 02/03/04 ship source-class parsers.

## Interface Contract for Wave 2 / Wave 3 Plans

This is the **load-bearing contract** the downstream plans consume — pinning it here so a planner of Plan 02/03/04/05 can read this section and know exactly what they have to do:

### Plans 02 (Reddit), 03 (Equipboard), 04 (YouTube) each:

1. Create `skills/patchbay-research/source_classes/<name>.py` exposing three callables:
   - `match_url(url: str) -> bool` — host pattern check, no I/O.
   - `fetch_tier1(url: str) -> dict` — typically `return fetch_tier1(rewritten_url)` from `scripts.fetch_tier1`. Reddit rewrites with `.json` suffix; Equipboard/YouTube pass-through.
   - `parse_to_chunks(fetch_result: dict, gear_ctx: dict) -> list[dict]` — convert the body into chunks conforming to `skills/patchbay-ingest/references/chunk-schema.md` § Required fields. Every chunk gets `tier_used: 1`.
2. Self-register at the bottom of the module:
   ```python
   from . import REGISTRY as _REGISTRY
   import sys as _sys
   _REGISTRY.append(_sys.modules[__name__])
   ```
3. Add EXACTLY ONE line to `source_classes/__init__.py`: `from . import <name>`. Wave 2 plans land commutatively because each adds a distinct import line.
4. The generic fallback module must be the LAST entry in `REGISTRY`; whichever plan adds it owns putting its `from . import generic` line last.

### Plan 05 (`--review-failures`):

1. Read `<gear_root>/<Brand Item>/knowledge/failures.log` line-by-line, parse each as JSON.
2. For each entry, show the user: URL + `reason` + `suggested_escalation` + `reason_detail` snippet.
3. Prompt for action: escalate to tier 2 (Claude_in_Chrome) / tier 3 (computer-use + vision) / paste manually (tier 0) / skip / defer. Use the `suggested_escalation` as the highlighted default.
4. On a successful escalation, append the new chunks via `scripts.write_chunk.write_chunks` (with `tier_used: 2|3|0` as appropriate) and append a new entry to `failures.log` with `retry_count` incremented and `last_attempted` set to now.

## Next Phase Readiness

- **Plans 02/03/04 can start immediately.** The three-callable contract is locked, the registry skeleton is empty, and the test harness pattern is in `test_core.py` to copy-adapt.
- **No blockers.** No spike findings or schema questions outstanding.
- **One thing to watch in Plans 02/03/04:** every parser MUST set `tier_used: 1` on every chunk. Add a one-line assertion to the GREEN test that verifies this — the test_core.py format makes it trivial.

## Self-Check: PASSED

Verification grep / file checks (all from the plan's `<verify>` lines):

- FOUND: skills/patchbay-research/SKILL.md
- FOUND: skills/patchbay-research/references/failures-log-schema.md
- FOUND: skills/patchbay-research/references/source-class-registry.md
- FOUND: skills/patchbay-research/scripts/fetch_tier1.py
- FOUND: skills/patchbay-research/scripts/log_failure.py
- FOUND: skills/patchbay-research/scripts/write_chunk.py
- FOUND: skills/patchbay-research/scripts/url_router.py
- FOUND: skills/patchbay-research/scripts/test_core.py
- FOUND: skills/patchbay-research/source_classes/__init__.py
- FOUND commits: 7901c65 (test RED), 3cc3fdc (Task 1 GREEN), 99652fa (Task 2)
- pytest: 12 passed, 0 failed
- grep `suggested_escalation` in failures-log-schema.md: 3+ matches
- grep `"either"` in failures-log-schema.md: present
- grep `match_url` + `parse_to_chunks` in source-class-registry.md: both present
- grep `ipaddress` in fetch_tier1.py: present
- grep `is_relative_to` in write_chunk.py: present
- grep `def update_chunk_field` in write_chunk.py: present
- grep `REGISTRY: list = []` in source_classes/__init__.py: present
- grep `^from \. import (reddit|equipboard|youtube)` in source_classes/__init__.py: NOT present (correct — Plans 02/03/04 add these)
- SKILL.md frontmatter, no-auto-fallback string, cloudflare-block, "either", cross_source_match_candidates, /patchbay:research --review-failures, ≥6 Step headings, UI layer notes, private IP, path-outside-gear_root: all present

---
*Phase: 03-patchbay-research-with-tiered-fetch*
*Completed: 2026-05-16*
