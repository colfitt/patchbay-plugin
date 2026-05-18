---
phase: 04-citation-tracking-recommendations
plan: 01
subsystem: citation-substrate
tags: [patchbay-research, citations, canonicalization, external_resource, citing_chunk_ids, write_chunk-hook, sweep, sha1-stable-id]

# Dependency graph
requires:
  - phase: 03-patchbay-research-with-tiered-fetch
    provides: write_chunks(chunks_jsonl_path, new_chunks, gear_root=None) + update_chunk_field + per-source-class external_resource emissions (reddit, equipboard)
provides:
  - canonicalize_url pure function (stdlib urllib only) — single source of truth for URL canonicalization
  - external_resource_sweep — post-write idempotent pass that guarantees CITATION-01 + CITATION-04 at the chunk-writer boundary
  - write_chunks now invokes the sweep on every append — Plan 02/03 can assume the substrate is always satisfied
  - Stable hash-based sweep-emitted chunk ids (ext-sweep-{sha1(canonical_url)[:8]}) — Plan 02's external_resource_chunk_id is cross-run stable
  - Reference doc locking the canonicalization scope, tier_used=None decision, resource_type override-on-merge rule, and idempotency contract
affects: [04-02-recommendations, 04-03-verified-promotion, phase-3-RESEARCH-01-queries]

# Tech tracking
tech-stack:
  added: []  # stdlib only — hashlib, urllib.parse, tempfile, json, re
  patterns:
    - "Post-write idempotent sweep at the writer boundary (one place, not per-parser)"
    - "Content-derived stable ids (sha1-prefix) for synthetic chunks — round-trip stable across re-runs"
    - "Authoritative classifier override on merge — sweep's _classify_resource_type wins over source-class parsers"
    - "tier_used = None as the honest 'did-not-fetch' signal, distinct from tier_used=0 (manual user-paste)"

key-files:
  created:
    - skills/patchbay-research/scripts/canonicalize_url.py
    - skills/patchbay-research/scripts/external_resource_sweep.py
    - skills/patchbay-research/scripts/test_canonicalize_url.py
    - skills/patchbay-research/scripts/test_external_resource_sweep.py
    - skills/patchbay-research/references/external-resource-sweep.md
  modified:
    - skills/patchbay-research/scripts/write_chunk.py  # added sweep import + call site at end of write_chunks
    - skills/patchbay-research/scripts/test_core.py    # Phase-3 regression fix: filter for type=='text' before count assertion

key-decisions:
  - "Sweep-emitted external_resource chunks set tier_used=None (NOT 0). The tier ladder reserves tier 0 for 'manual user-paste escape hatch' — a different semantic. None is the honest 'did not fetch' signal."
  - "Sweep-emitted chunk ids are content-derived sha1 prefixes (ext-sweep-{sha1(canonical_url)[:8]}). A monotonic counter would re-issue the same id for a DIFFERENT URL when discovery order changes across runs — hash-based ids are round-trip stable, which Plan 02's Recommendation.external_resource_chunk_id depends on. W5 mitigation."
  - "Sweep's _classify_resource_type is AUTHORITATIVE on merge — overwrites source-class parser classifications (reddit.py emits 'article' for reddit-post URLs; sweep overwrites to 'reddit-post'). Tech debt: a future refactor could extract a shared classify_url helper used by both reddit.py and the sweep."
  - "Canonicalization scope locked at v2.0: reject non-http(s) schemes (return ''); YouTube short↔long collapse; strip si/utm_*/feature/fbclid/gclid/mc_* tracking; strip single trailing slash; drop fragment; lowercase scheme+host; sort remaining query params."
  - "Sweep call site lives in write_chunks (the writer boundary), NOT in each source-class parser. One place to fix means a future fifth source class inherits CITATION-01 for free."
  - "No try/except wrapper around the sweep call — sweep failure surfaces because data-layer integrity beats silent partial writes."
  - "cross_source_match_candidates is name-based (verified against write_chunk.compute_cross_source_matches L135-L186), so dedup-by-canonical-url in the sweep is safe — dropping a duplicate external_resource by id never leaves a dangling reference."

patterns-established:
  - "Post-write idempotent sweep: read chunks.jsonl → mutate in-memory → atomic rewrite (tempfile.mkstemp + os.replace, mirrors update_chunk_field). Re-running produces a byte-identical file."
  - "Content-derived stable ids for synthetic chunks: sha1-prefix gives round-trip identity without a side-channel id counter."
  - "Trailing-punctuation strip before canonicalization: URL_RE permissively captures URLs in prose, then .rstrip('.,;:!?)') before canonicalize_url handles sentence-ending punctuation."

requirements-completed: [CITATION-01, CITATION-04]

# Metrics
duration: 5min
completed: 2026-05-17
---

# Phase 04 Plan 01: Citation substrate (canonicalize_url + external_resource_sweep) Summary

**Locked the load-bearing citation substrate Phase 4 builds on: a pure-function URL canonicalizer + a post-write idempotent sweep that guarantees every external URL in chunks.jsonl has exactly one external_resource chunk with canonical .url and complete citing_chunk_ids — invoked from write_chunks at the writer boundary, so Plans 02/03 (and future source classes) inherit CITATION-01 + CITATION-04 for free.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-18T00:52:08Z
- **Completed:** 2026-05-18T00:57:27Z
- **Tasks:** 2 completed
- **Files created:** 5
- **Files modified:** 2

## Accomplishments

- **canonicalize_url** — stdlib-only pure function (urllib.parse) locks the single source of truth for URL canonicalization at v2.0. 12 test functions (16 collected with parametrize) cover YouTube short↔long collapse, ?si= and utm_* tracking strip, trailing-slash strip, host/scheme lowercasing, idempotency, fragment drop, and non-http(s) scheme rejection (T-04-01 mitigation: returns "" so callers can filter).
- **external_resource_sweep** — post-write idempotent pass invoked from `write_chunks` AFTER the append loop. Reads chunks.jsonl, builds the citation graph keyed by canonical URL, atomically rewrites via tempfile.mkstemp + os.replace (T-04-04 mitigation). 14 test cases cover backfill, merge into populated citing_chunk_ids, canonicalization of existing external_resource urls, dedup-by-canonical-url, resource_type override-on-merge, idempotency (byte-identical re-runs), and the write_chunks integration path.
- **write_chunks hook** — single line added at the end of `write_chunks` before return: `ensure_external_resource_chunks(str(resolved), gear_root=gear_root)`. No try/except — sweep failures surface. One place to fix means a future fifth source class inherits CITATION-01 for free.
- **Reference doc** (`references/external-resource-sweep.md`) — locks the canonicalization scope, tier_used=None decision, sweep-emitted id scheme, resource_type override-on-merge rule, idempotency contract, threat mitigations, and the explicit "what it does NOT do" list (does not fetch, does not promote trust, does not enrich creator/title/updated, does not recurse into external_resource chunks). Plan 02 + Plan 03 read this doc to learn the substrate they consume.

## Task Commits

1. **Task 1 RED — canonicalize_url contract (12 cases)** — `a77ff9a` (test)
2. **Task 1 GREEN — canonicalize_url implementation (12 cases)** — `7bea9c0` (feat)
3. **Task 2 RED — external_resource_sweep contract (14 cases)** — `2d1503a` (test)
4. **Task 2 GREEN — sweep + write_chunks hook + Phase-3 regression fix (14 cases)** — `05af467` (feat)

_TDD cycle: RED → GREEN for each task; no REFACTOR commits needed (implementations satisfied all cases on first GREEN pass)._

## Files Created/Modified

**Created:**
- `skills/patchbay-research/scripts/canonicalize_url.py` — pure-function URL canonicalizer (stdlib only, ~90 LOC)
- `skills/patchbay-research/scripts/external_resource_sweep.py` — post-write idempotent sweep + extract_urls_from_chunk helper
- `skills/patchbay-research/scripts/test_canonicalize_url.py` — 12 pytest cases (16 collected with parametrize)
- `skills/patchbay-research/scripts/test_external_resource_sweep.py` — 14 pytest cases
- `skills/patchbay-research/references/external-resource-sweep.md` — substrate doc locked at v2.0

**Modified:**
- `skills/patchbay-research/scripts/write_chunk.py` — added sweep import (try/except ImportError fallback) and `ensure_external_resource_chunks(str(resolved), gear_root=gear_root)` call at end of `write_chunks`
- `skills/patchbay-research/scripts/test_core.py` — Phase-3 regression fix in `test_write_chunks_appends_jsonl`: now filters lines for `type=='text'` before asserting count == 2 (the sweep correctly adds 2 synthetic external_resource chunks for the 2 referenced URLs — Phase-3 test predates the sweep)

## Decisions Made

All key decisions captured in frontmatter `key-decisions`. Highlights:

- **tier_used = None on sweep-emitted chunks** — the spike-findings tier ladder reserves `tier_used=0` for "manual user-paste (escape hatch)" — a DIFFERENT semantic from a synthetic-derived sweep chunk. None is the honest "did-not-fetch" signal; downstream consumers treat None as "did not fetch."
- **Stable hash-based ids** — `ext-sweep-{sha1(canonical_url)[:8]}` is content-derived and round-trip stable; a monotonic counter would re-issue the same id for a DIFFERENT URL when discovery order changes across runs. Plan 02's `Recommendation.external_resource_chunk_id` (and Plan 03's verify lookup) depend on this stability.
- **Resource-type override on merge** — sweep's `_classify_resource_type` is authoritative; overwrites source-class parser classifications. Locked at v2.0 as the load-bearing fix; tech debt noted (a follow-up could extract a shared `classify_url` helper used by both reddit.py and the sweep, but that's a Phase-5+ refactor candidate).
- **Sweep hook at writer boundary, not per-parser** — one place to fix CITATION-01 means a future fifth source class inherits the guarantee for free.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Phase-3 regression in test_core.test_write_chunks_appends_jsonl**
- **Found during:** Task 2 Step 7 (smoke-run the full research test suite)
- **Issue:** `test_write_chunks_appends_jsonl` asserted `len(lines) == 2` after writing 2 text chunks. The sweep now correctly adds 2 synthetic external_resource chunks (one for each referenced URL: equipboard.com and reddit.com URLs in the chunks' `provenance.url`), so the file legitimately contains 4 lines.
- **Fix:** Filter lines for `type=='text'` before asserting count == 2 and before pulling `cross_source_match_candidates`. The sweep behavior is the correct new contract; the test's expectation predated Plan 04-01.
- **Files modified:** `skills/patchbay-research/scripts/test_core.py`
- **Verification:** Full Phase-3 + Plan 04-01 test suite passes (103 tests). Phase 3 plan-doc Step 7 explicitly anticipated this: "If any Phase 3 test asserts on tier_used of a sweep-emitted chunk... fix it inline."
- **Committed in:** `05af467` (part of Task 2 GREEN commit)

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** None — this was an anticipated correctness fix at the boundary of new sweep behavior. The plan explicitly authorized the inline fix in Task 2 Step 7.

## Issues Encountered

**Accidental commit on main branch (caught and recovered safely; surface as cleanup note for orchestrator/user):**

- **Root cause:** The first invocation of `git commit` for the RED commit on Task 1 was prefixed with `cd /Users/cfitt/Dev/patchbay-plugin && ...` in a Bash tool call. The `cd` moved the shell into the MAIN repo (which has a real `.git` directory) rather than staying in the worktree. The commit landed on `main` (worktree HEAD was untouched).
- **Detection:** Post-commit `git log` showed an unexpected new commit on main, but worktree branch state was unchanged.
- **Recovery (safe path taken):** Cherry-picked the same change content (`c7fe303` on main) onto the worktree branch as `a77ff9a`. **NO destructive operations on `main` were performed** — per the protocol's absolute prohibition on `git update-ref refs/heads/<protected>`. Main is now one commit ahead of its prior HEAD (`6660024`) with an extra commit (`c7fe303`) that is functionally identical to the worktree's `a77ff9a` and will deduplicate naturally when the orchestrator merges the worktree branch back to main.
- **Mitigation for the rest of this session:** All subsequent Bash calls used relative invocation from the worktree's cwd — NO `cd` operations were issued in any subsequent Bash tool call. The pre-commit HEAD assertion confirmed each subsequent commit landed on `worktree-agent-af9b37c3f0bd49403`.
- **Action requested from orchestrator/user at merge time:** When merging this worktree branch back to main, the orchestrator can simply note that main's `c7fe303` is content-identical to the worktree's `a77ff9a` — no special action needed beyond a normal merge (git will recognize the duplicate). If the user prefers a clean main history, a `git reset --keep 6660024` on main BEFORE the merge would drop `c7fe303` and let the worktree's `a77ff9a` land cleanly through the merge (this preserves the user's uncommitted working-tree edits to STATE.md and 03-05-SUMMARY.md, unlike `--hard`).

## User Setup Required

None — pure-function + stdlib-only sweep with no external service configuration required.

## Next Phase Readiness

**Plan 04-02 (recommendations) is unblocked:**
- `aggregate_citations` can read `chunks.jsonl`, filter for `type == "external_resource"`, and group by `content.url` (now guaranteed canonical) — no ad-hoc canonicalization needed.
- `Recommendation.external_resource_chunk_id` is cross-run stable thanks to `ext-sweep-{sha1(...)[:8]}` ids.
- `tier_used is None` filters work correctly to distinguish "fetched" chunks (tier_used in {1,2,3}) from sweep-synthetic chunks.

**Plan 04-03 (verified promotion) is unblocked:**
- `verify_resource(chunk_id)` can look up an external_resource chunk by stable hash id.
- `update_chunk_field(chunks_path, chunk_id, "content.creator", ...)` and similar enrichment ops work against the sweep's empty-default fields (creator="", title="", updated=None).
- The plan's `trust=` parameter (which Plan 04-03 will add to write_chunks) is forward-compatible — it does not affect the sweep call site.

**No blockers or concerns.** Phase-3 regression test was fixed inline as authorized by the plan. Full Phase 3 + Plan 04-01 test suite (103 cases) is green.

---
*Phase: 04-citation-tracking-recommendations*
*Completed: 2026-05-17*

## TDD Gate Compliance

Both tasks followed the RED → GREEN cycle. Plan-level TDD gates in `git log`:
- Task 1: `a77ff9a` (test: RED) → `7bea9c0` (feat: GREEN) ✓
- Task 2: `2d1503a` (test: RED) → `05af467` (feat: GREEN) ✓
- No REFACTOR commits — both GREEN implementations passed all cases on first run without rework.

## Self-Check: PASSED

**File existence (8/8):**
- FOUND: `skills/patchbay-research/scripts/canonicalize_url.py`
- FOUND: `skills/patchbay-research/scripts/external_resource_sweep.py`
- FOUND: `skills/patchbay-research/scripts/test_canonicalize_url.py`
- FOUND: `skills/patchbay-research/scripts/test_external_resource_sweep.py`
- FOUND: `skills/patchbay-research/references/external-resource-sweep.md`
- FOUND: `skills/patchbay-research/scripts/write_chunk.py` (modified — sweep hook added)
- FOUND: `skills/patchbay-research/scripts/test_core.py` (modified — Phase-3 regression fix)
- FOUND: `.planning/phases/04-citation-tracking-recommendations/04-01-SUMMARY.md`

**Commit hashes (4/4):**
- FOUND: `a77ff9a` — test(04-01): RED — canonicalize_url contract (12 cases)
- FOUND: `7bea9c0` — feat(04-01): GREEN — canonicalize_url (12 cases)
- FOUND: `2d1503a` — test(04-01): RED — external_resource_sweep contract (14 cases)
- FOUND: `05af467` — feat(04-01): GREEN — external_resource sweep + write_chunks hook (14 cases)
