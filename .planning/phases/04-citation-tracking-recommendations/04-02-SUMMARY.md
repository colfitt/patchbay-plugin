---
phase: 04-citation-tracking-recommendations
plan: 02
subsystem: citations-recommendation-surface
tags: [patchbay-research, citations, recommendations, terminal-output, n-threshold, independent-sources, citation-02]

# Dependency graph
requires:
  - phase: 04-citation-tracking-recommendations
    plan: 01
    provides: external_resource_sweep guaranteeing CITATION-01 + CITATION-04 at every write_chunks call — every URL in chunks.jsonl has exactly one external_resource chunk with canonical content.url and complete citing_chunk_ids; sweep-emitted ids are stable (ext-sweep-<sha1[:8]>)
  - phase: 04-citation-tracking-recommendations
    plan: 01
    provides: canonicalize_url pure function — citations.py uses it on --filter-url input + on every URL match scanned from citing chunks
provides:
  - aggregate_citations(chunks_path, threshold=2, filter_url=None) -> list[Recommendation] — groups external_resource chunks by canonical URL, applies distinct-source N-threshold, returns sorted Recommendation list
  - format_recommendations_markdown(recommendations, gear, threshold) -> str — locked markdown output shape incl. empty-result wording
  - Recommendation dataclass — locked output contract Plan 04-03 consumes verbatim
  - /patchbay:research --citations <gear> CLI surface (citations.py __main__) — default threshold=2, configurable via --threshold flag (wins) or PATCHBAY_CITATION_THRESHOLD env var; --json mode emits Recommendation array for Plan 04-03 ingestion
  - references/citations-flow.md — locked subcommand surface doc (invocation, threshold semantics, output shape, known v2.0 limitation, UI layer notes table)
affects: [04-03-verified-promotion]

# Tech tracking
tech-stack:
  added: []  # stdlib only — argparse, json, os, re, sys, dataclasses, pathlib
  patterns:
    - "Public-entry-point defensive re-sort: aggregate_citations sorts, AND format_recommendations_markdown re-sorts before rendering — the formatter is independently callable and must enforce display ordering regardless of input order"
    - "Distinct-source counting at the trust boundary: count citing_chunk[source] values, not raw len(citing_chunk_ids) — a single source spamming N references cannot inflate the threshold (T-04-08 mitigation)"
    - "External_resource chunks ignored as citation voters: an external_resource is a TARGET, not a SOURCE — counting one would inflate the threshold from inside the citation graph"
    - "Argparse default = env-or-default(): default=_default_threshold_from_env() so env-var override works without a per-call branch, and flag-overrides-env falls out for free because argparse only honors default when the flag is absent"
    - "Subprocess-based CLI tests: spawn citations.py via sys.executable, set env var via env={} kwarg, parse stdout — proves the CLI surface end-to-end without test-time monkeypatching"

key-files:
  created:
    - skills/patchbay-research/scripts/citations.py
    - skills/patchbay-research/scripts/test_citations.py
    - skills/patchbay-research/references/citations-flow.md
  modified:
    - skills/patchbay-research/SKILL.md  # purely additive (+20 lines, 0 deletions): one new 'read these references' bullet, one new invocation-patterns row, one new H3 subsection in Process

key-decisions:
  - "Distinct-source rule counts citing_chunk[source] values, NOT raw len(citing_chunk_ids). The external_resource's own source is NOT counted. External_resource chunks citing other external_resources are IGNORED (citation TARGET, not SOURCE — vote-inflation prevention). Spec mandate from <interfaces>; T-04-08 mitigation."
  - "Empty-result message LOCKED at v2.0 per W3: 'No citation recommendations at threshold N=<N> for <gear>. Try --threshold 1 to see all external resources.' Does NOT suggest re-running /patchbay:research — that would misdirect since the user has just run it to populate the substrate this command queried."
  - "Default threshold derivation: argparse default=_default_threshold_from_env() resolves PATCHBAY_CITATION_THRESHOLD if it's a positive integer, else 2. The CLI flag overrides because argparse only honors `default` when the flag is absent. No explicit precedence branch needed."
  - "format_recommendations_markdown defensively re-sorts by (-source_count, canonical_url) on entry. aggregate_citations already sorts, but the formatter is a public entry point — Plan 04-03 or tests may build Recommendation lists by hand. The display rule (3-source rec before 2-source rec) must hold regardless of input order."
  - "Recommendation dataclass shape is LOCKED at v2.0 per Plan 04-02 <interfaces>. Plan 04-03 (verified promotion) keys off `external_resource_chunk_id`, which is stable across re-runs thanks to Plan 04-01's sha1-prefix sweep-emitted ids."
  - "--filter-url canonicalizes user input before comparison. A non-http(s) filter URL canonicalizes to '' and short-circuits the result set to [] (T-04-07 mitigation: hostile filter input cannot widen the result set)."
  - "--json emits asdict(Recommendation) via json.dumps(..., ensure_ascii=False, indent=2). RFC-8259 escaping is the trust boundary against terminal/downstream injection (T-04-11 disposition: accept)."
  - "Known v2.0 limitation explicitly documented in references/citations-flow.md and must_haves.known_limitations: distinct-source count may under-count true independence when same-class chunks dominate (e.g., Equipboard re-publishing a YouTube reviewer's transcript = 1 source 'equipboard', not 2). Proper primary-source independence tracking is deferred to a future phase. CITATION-02 acceptance bar — multi-source corroboration observable — is met; the precision floor is good-enough for v2.0."

patterns-established:
  - "Argparse default from env helper: _default_threshold_from_env() returns int(env) if env.isdigit() and int(env) >= 1, else 2 — concentrates env-vs-default logic in one helper, lets argparse handle flag-overrides-env for free"
  - "Recommendation dataclass with dataclasses.asdict for JSON serialization: lets the formatter and the CLI share the same shape, lets Plan 04-03 consume the same shape via json.loads, no manual to_dict serializer drift"

requirements-completed: [CITATION-02]

# Metrics
duration: 8min
completed: 2026-05-17
---

# Phase 04 Plan 02: Citation-recommendation surface (`/patchbay:research --citations`) Summary

**Shipped the user-visible citation-recommendation surface: `/patchbay:research --citations <gear>` walks the gear's chunks.jsonl, groups external_resource chunks by canonical URL, applies the N-threshold over DISTINCT citing-chunk sources (not raw citing_chunk_ids count), and prints a markdown block (or JSON with `--json`) to stdout. CITATION-02's "observable in terminal output, not buried in a log file" constraint is enforced — empty results still print a single guidance line and exit 0; silent success is not allowed.**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2 completed
- **Files created:** 3 (citations.py, test_citations.py, citations-flow.md)
- **Files modified:** 1 (SKILL.md — purely additive, +20 lines, 0 deletions)
- **Tests added:** 20 (full suite now 123 passed, 0 failed)

## Accomplishments

- **citations.py** (~480 LOC including module docstring) — pure-Python aggregator + markdown formatter + CLI entry point. stdlib only (argparse, json, os, re, sys, dataclasses, pathlib). Imports `canonicalize_url` from Plan 04-01 via the same try/except ImportError fallback the sweep uses.
- **aggregate_citations** — reads chunks.jsonl (defensively, skipping malformed lines), builds an id→chunk map, iterates external_resource chunks, applies the distinct-source N-threshold over each chunk's `citing_chunk_ids`, and emits a Recommendation list sorted by (-independent_source_count, canonical_url). External_resource chunks citing other external_resources are ignored as voters (citation TARGET, not SOURCE — vote-inflation prevention). Citing-chunk references whose ids cannot be resolved in `by_id` are skipped, so an external_resource with only unresolvable citing_chunk_ids is filtered out at threshold>=1.
- **format_recommendations_markdown** — locked output shape: `# Citation recommendations for <gear> (threshold N=<N>)` header, per-rec `## N. <canonical_url> — referenced X times across Y sources` blocks with type / creator / title / citing-chunks list. Defensive re-sort on entry guarantees the display rule (3-source rec before 2-source rec) holds even when called with hand-built Recommendation lists.
- **Empty-result wording LOCKED** at v2.0 per W3: `"No citation recommendations at threshold N=<N> for <gear>. Try --threshold 1 to see all external resources."` Does NOT suggest re-running `/patchbay:research` — the user just ran that to populate the substrate this command queried.
- **CLI surface**: `python3 citations.py <chunks_path> --gear "<Brand Item>" [--threshold N] [--filter-url URL] [--json]`. Default threshold = `int(PATCHBAY_CITATION_THRESHOLD)` if it's a positive integer, else 2. `--threshold` CLI flag wins env. `--json` emits `json.dumps([asdict(r) for r in recs], ensure_ascii=False, indent=2)`. Exit code 0 on success including the no-results case; argparse errors only on argument parsing.
- **test_citations.py** — 20 pytest cases covering aggregate (10), formatter (5), and CLI (5 via subprocess). One iteration on Task 1 GREEN: the formatter needed defensive re-sort on entry (test 15: `test_format_orders_recommendations_by_source_count_desc` — a hand-built Recommendation list in test-only context).
- **references/citations-flow.md** (new) — locks the subcommand surface at v2.0: invocation, threshold semantics (incl. distinct-source rule + the known v2.0 same-class-undercount limitation), markdown + JSON output shape, locked empty-result wording, relationship-to-other-subcommands table, parallel UI layer notes.
- **SKILL.md** (additive) — new bullet in "read these reference files" list, new row in "Invocation patterns" code block for `--citations`, new H3 subsection "Step: Surface cross-source citation recommendations (--citations)" at the end of the Process flow. All Plan 03-01/05 content preserved verbatim (verified: `--review-failures`, `failures-log-schema.md` references still present).

## Task Commits

1. **Task 1 RED — citations aggregator + CLI (20 cases)** — `1c0a168` (test)
2. **Task 1 GREEN — aggregate_citations + CLI (20 cases)** — `791bdf1` (feat)
3. **Task 2 — SKILL.md + citations-flow reference for --citations subcommand** — `abec8c1` (docs)

_TDD cycle: RED → GREEN for Task 1; no REFACTOR commit was needed (the one minor adjustment — defensive re-sort in the formatter — landed inside the GREEN commit since the implementation was still being written, no behavior had shipped yet)._

## Files Created/Modified

**Created:**
- `skills/patchbay-research/scripts/citations.py` — aggregator + markdown formatter + CLI (~480 LOC; stdlib only).
- `skills/patchbay-research/scripts/test_citations.py` — 20 pytest cases (10 aggregate, 5 formatter, 5 CLI via subprocess).
- `skills/patchbay-research/references/citations-flow.md` — locked subcommand reference (invocation, threshold semantics + known v2.0 limitation, output shape, UI layer notes).

**Modified:**
- `skills/patchbay-research/SKILL.md` — purely additive (+20 lines, 0 deletions): "read these references" bullet, "Invocation patterns" row, new H3 subsection at end of Process flow.

## Locked contracts (consumed by Plan 04-03)

### Recommendation dataclass

```python
@dataclass
class Recommendation:
    canonical_url: str              # output of canonicalize_url
    resource_type: str              # "youtube"|"article"|"reddit-post"|"image"|"other"
    creator: str                    # may be ""
    title: str                      # may be ""
    independent_source_count: int   # the value compared against threshold
    citing_chunks: list             # [{id, source, excerpt}] sorted by (source, id)
    external_resource_chunk_id: str # stable cross-run via sha1-prefix sweep ids (Plan 04-01)
```

### Distinct-source rule (load-bearing)

- Count DISTINCT values of `citing_chunk["source"]` across the chunks named in `citing_chunk_ids`.
- The external_resource chunk's OWN `source` field is NOT counted.
- External_resource chunks cited by other external_resources are IGNORED (target, not source — vote-inflation prevention).

### CLI surface

| Flag                 | Type / default                                                        | Behavior                                                                    |
|----------------------|-----------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `chunks_path` (pos)  | `Path` (required)                                                     | Path to the per-gear chunks.jsonl                                           |
| `--gear`             | `str` (required)                                                      | Brand + item label shown in output                                          |
| `--threshold`        | `int`; default = `int(PATCHBAY_CITATION_THRESHOLD)` if env is digit, else 2 | Minimum DISTINCT citing-chunk sources; flag wins env                  |
| `--filter-url`       | `str`; default `None`                                                  | Restrict to recommendations whose canonical URL == canonicalize_url(input)  |
| `--json`             | `store_true`                                                          | Emit JSON array of Recommendation dicts instead of markdown                  |
| **exit code**        | 0 on success (INCLUDING no-results); non-zero only on argparse errors | -                                                                            |

### Locked empty-result message (W3 fix)

```
No citation recommendations at threshold N=<threshold> for <gear>. Try --threshold 1 to see all external resources.
```

Does NOT include any "run /patchbay:research" clause. Verified by `test_format_empty_recommendations_message`.

### Markdown output structure

```
# Citation recommendations for <gear> (threshold N=<N>)

Showing K resource(s) cited by >= N independent sources.

## 1. <canonical_url> — referenced X times across Y sources
- type: <resource_type>
- creator: <creator>            (only when non-empty)
- title: <title>                (only when non-empty)
- citing chunks:
  - [<source>] <chunk_id> — "<excerpt>"
  - [<source>] <chunk_id> — "<excerpt>"

## 2. ...
```

Recommendations are ordered by `(-independent_source_count, canonical_url)`; citing-chunks within each recommendation are ordered by `(source, id)`.

## Decisions Made

All key decisions captured in frontmatter `key-decisions`. Highlights:

- **Distinct-source rule, not raw count.** A single source spamming N references to the same URL cannot trip an N-threshold; only N truly distinct sources can. Counter-example (one Reddit thread emitting 5 external_resource refs to one YouTube video) is in the v2.0 test suite (`test_aggregate_counts_distinct_sources_not_raw_ids`).
- **Empty-result wording LOCKED at v2.0 per W3.** The previous draft suggested "run /patchbay:research <gear>"; that misdirects because the user just ran it. The current wording lowers the friction the right way: "Try --threshold 1 to see all external resources."
- **Defensive re-sort in the formatter.** aggregate_citations sorts, but the formatter is a public entry point — Plan 04-03's verified-promotion preview, hand-built test fixtures, and any future caller may pass an unsorted list. The display rule must be enforced where the display happens.
- **External_resource chunks ignored as voters.** An external_resource is a citation TARGET. Counting one would let a chunk vote for itself transitively — the distinct-source threshold becomes inflatable from inside the graph.
- **Known v2.0 limitation explicitly documented**: the same-class re-publication case (Equipboard re-publishing a YouTube reviewer = 1 source, not 2). Deferred to a future phase per W4. CITATION-02's acceptance bar is met; precision floor is good-enough for v2.0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Formatter must re-sort recommendations on entry**

- **Found during:** Task 1 GREEN, first pytest pass (19/20 passing; `test_format_orders_recommendations_by_source_count_desc` failed).
- **Issue:** The plan's `format_recommendations_markdown` spec didn't explicitly state that the formatter must sort. The aggregator sorts before returning, so passing aggregator output through the formatter "just works" — but the test builds Recommendations by hand in unsorted order (2-source then 3-source) and asserts the 3-source one appears first in output. The formatter is a public entry point and Plan 04-03 (verified-promotion preview) will likely call it with hand-built lists.
- **Fix:** Added a defensive `sorted(..., key=lambda r: (-r.independent_source_count, r.canonical_url))` at the entry of `format_recommendations_markdown`. This is consistent with the documented display rule and the aggregator's own sort key.
- **Files modified:** `skills/patchbay-research/scripts/citations.py` (one block, ~7 lines added inside the GREEN commit before any prior version had shipped).
- **Verification:** All 20 tests green; full research suite (123 tests) regression-free.
- **Committed in:** `791bdf1` (the same GREEN commit — the formatter had not yet shipped to disk in any prior commit, so this is one cohesive Task 1 GREEN landing, not a separate refactor).

**Total deviations:** 1 auto-fixed (Rule 1)
**Impact on plan:** None — clarification of an under-specified public-entry-point invariant. Documented in the dataclass-level `key-decisions` for future readers.

### Worktree merge fast-forward

The worktree branch (`worktree-agent-a9edfd8d19f420768`) was forked from `main` BEFORE Plan 04-01 merged. Before starting Task 1 RED, the executor fast-forward-merged `main` into the worktree branch to pick up the Plan 04-01 substrate (canonicalize_url.py, external_resource_sweep.py, write_chunk.py hook, etc.). The merge was a clean fast-forward (no conflicts, no merge commit) and is reflected in the log between `e6e19dd` (worktree's prior HEAD) and `c760615` (`chore: merge executor worktree (wave 1 — plan 04-01)`).

### Tool-call pathing detour (Write to absolute path)

The first Write call for `test_citations.py` used the path `skills/patchbay-research/scripts/test_citations.py` (without a working-directory-anchored absolute prefix) and the Write tool's resolution landed it in the MAIN repo's working tree rather than the worktree's. This was detected by the post-commit assertion (ls failed in the worktree). The recovery was a single `mv` to relocate the file from the main repo's working tree into the worktree's working tree. The MAIN repo's git status reflected this only as an "untracked file" that was then removed by the `mv`; no main-repo commit was created. From that point on, every Write/Edit used the worktree absolute prefix `/Users/cfitt/Dev/patchbay-plugin/.claude/worktrees/agent-a9edfd8d19f420768/...`. This is a session-level operational note, not a code or content concern.

## Issues Encountered

None beyond the operational notes above (worktree fast-forward + Write-pathing detour). Both are session-level mechanics; neither affects code correctness.

## User Setup Required

None — pure-stdlib aggregator + CLI; no external service configuration required.

## Next Phase Readiness

**Plan 04-03 (verified promotion) is unblocked:**

- The `Recommendation` dataclass shape is locked. Plan 04-03's `--verify <gear> <url>` subcommand can canonicalize the user-provided URL, scan `chunks.jsonl` for the matching `external_resource_chunk_id` (stable across re-runs per Plan 04-01's sha1-prefix ids), and apply a verified-trust upgrade via `update_chunk_field`.
- The `--json` mode emits the dataclass as a JSON array — Plan 04-03 can pipe `--citations --json | jq` into its own selector flow, OR call `aggregate_citations` directly as a Python import. Both paths are equivalent.
- The locked `external_resource_chunk_id` field (cross-run stable hash-prefix id) is the key Plan 04-03 keys verification against — no lookup-by-URL drift.

**No blockers or concerns.** Full Phase 3 + Plan 04-01 + Plan 04-02 test suite (123 cases) is green.

---
*Phase: 04-citation-tracking-recommendations*
*Completed: 2026-05-17*

## TDD Gate Compliance

Task 1 followed the RED → GREEN cycle. Plan-level TDD gates in `git log`:
- Task 1: `1c0a168` (test: RED) → `791bdf1` (feat: GREEN) ✓
- Task 2: `abec8c1` (docs) — Task 2 is doc-only, no TDD gates required by the plan.

No REFACTOR commit — the one in-task adjustment (defensive re-sort in the formatter) landed inside the GREEN commit before any prior version of the formatter had shipped to disk.

## Self-Check: PASSED

**File existence (4/4):**
- FOUND: `skills/patchbay-research/scripts/citations.py`
- FOUND: `skills/patchbay-research/scripts/test_citations.py`
- FOUND: `skills/patchbay-research/references/citations-flow.md`
- FOUND: `skills/patchbay-research/SKILL.md` (modified — additive)

**Commit hashes (3/3):**
- FOUND: `1c0a168` — test(04-02): RED — citations aggregator + CLI (20 cases)
- FOUND: `791bdf1` — feat(04-02): GREEN — aggregate_citations + CLI (20 cases)
- FOUND: `abec8c1` — docs(04-02): SKILL.md + citations-flow reference for --citations subcommand

**Test suite:** `python3 -m pytest skills/patchbay-research/scripts/ -v` → **123 passed**, 0 failed.

**Acceptance grep checks (all pass):**
- `grep -q "independent_source_count" skills/patchbay-research/scripts/citations.py` ✓
- `grep -q "PATCHBAY_CITATION_THRESHOLD" skills/patchbay-research/scripts/citations.py` ✓
- `grep -q "threshold N=" skills/patchbay-research/scripts/citations.py` ✓
- `grep -q "No citation recommendations at threshold N=" skills/patchbay-research/scripts/citations.py` ✓
- W3 fix check (empty-result message does NOT mention re-running /patchbay:research) ✓
- `grep -q -- "--citations" skills/patchbay-research/SKILL.md` ✓
- `grep -q "citations-flow.md" skills/patchbay-research/SKILL.md` ✓
- `grep -q "PATCHBAY_CITATION_THRESHOLD" skills/patchbay-research/SKILL.md` ✓
- `grep -q "CITATION-02" skills/patchbay-research/references/citations-flow.md` ✓
- `grep -q "DISTINCT" skills/patchbay-research/references/citations-flow.md` ✓
- `grep -q "Known v2.0 limitation" skills/patchbay-research/references/citations-flow.md` ✓
- `grep -q "/patchbay:research --review-failures" skills/patchbay-research/SKILL.md` (preserve) ✓
- `grep -q "failures-log-schema.md" skills/patchbay-research/SKILL.md` (preserve) ✓

**End-to-end behavioral check (per plan acceptance):** seeded a two-source citation scenario (reddit + equipboard cite same YouTube URL), ran `python3 citations.py <path> --gear "Test Gear"`, stdout contained the literal substring `referenced 2 times across 2 sources`. ✓
