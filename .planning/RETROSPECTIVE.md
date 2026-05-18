# Retrospective — patchbay-plugin

A living record of what was built, what worked, what didn't, and the patterns that emerged along the way.

## Milestone: v2.0 — gear-knowledge

**Shipped:** 2026-05-18
**Phases:** 3 (Phase 2, 3, 4) | **Plans:** 8 | **Tasks:** 17
**Audit status:** TECH_DEBT (24/24 requirements satisfied, 5/5 E2E flows pass, 138/138 pytest cases green)

### What Was Built

A unified gear-knowledge substrate that turns a piece of gear into a per-gear `chunks.jsonl` populated from manuals, web articles, Reddit threads, Equipboard pages, and YouTube videos — with citation tracking and verified-promotion baked in.

- **Phase 2** locked the chunk schema and shipped `patchbay:ingest` for manual PDFs (the simplest source class). Schema is additive-only: new source classes added in Phase 3 wrote to the same JSONL without a single field rename.
- **Phase 3** shipped `patchbay:research <gear>` with four source classes (Reddit `.json` cheap-path, Equipboard JSON-LD + DOM fallback, YouTube multimodal, generic articles), a tier-1 / 2 / 3 / 0 fetch ladder, append-only `failures.log` with structured escalation hints, and an interactive `--review-failures` flow that **never auto-falls-back** between tiers — every escalation is user-driven.
- **Phase 4** closed the citation loop with three plans: URL canonicalization + post-write `external_resource` sweep (CITATION-01 + CITATION-04 inherited for free by every source class), `--citations` recommendation surface with distinct-source threshold, and `--verify` orchestrator that re-ingests via the Phase 3 url_router and promotes resulting chunks to `trust="high"`.

### What Worked

- **Spike-driven architecture validation before plan-phase.** Six spikes (001 / 002a / 002c / 003 / 003b / 003c) locked the chunk schema, fetch-tier ladder, and per-source-class blueprints before any execution. The schema didn't change once during Phases 2-4. Plan checkers caught interface drift against deployed code (write_chunks / update_chunk_field signature mismatches in Phase 4 iter 1) because the spike findings established a single source of truth they could cross-reference.
- **Self-registering source-class registry pattern** (Phase 3 Plan 01 → Plans 02/03/04). Each new source class adds one import line to `__init__.py` via single-line read-modify-write append. Result: commutative merges across Wave 2's three plans, zero conflicts.
- **TDD discipline in Phase 4.** Every plan opened with a RED commit (failing tests defining the contract), then a GREEN commit (minimum code to pass). Plan-checker iteration 2 caught nothing because iteration 1's revision was guided by failing test names — the planner couldn't hand-wave around "make the test pass."
- **Sweep at the writer boundary** (Phase 4 Plan 01). Instead of patching three source classes to emit `external_resource` chunks correctly, the sweep hooks into `write_chunks` once. All source classes — including future ones — inherit CITATION-01 + CITATION-04 with zero code changes.
- **Worktree-isolated execution.** Each Phase 4 wave ran in its own git worktree → merged back cleanly. No cross-plan contamination, atomic per-plan commits, easy rollback if a wave failed.
- **Goal-backward verifier.** Phase 4's verifier traced the call graph end-to-end from `/patchbay:research --verify` → `_main` → `verify_resource()` → `route_url()` → `fetch_tier1` → `parse_to_chunks` → `promote_chunks_to_high_trust` → `write_chunks(trust="high")` → two `update_chunk_field` calls. That proved the chain works without running it.

### What Was Inefficient

- **Plan 04-01 BLOCKERs from interface drift.** The first planner pass wrote `write_chunks(chunks, chunks_path, *, gear_root=None)` — but the deployed function was `write_chunks(chunks_jsonl_path, new_chunks, gear_root=None)` (path FIRST). Same with `update_chunk_field`: documented as tuple `field_path`, deployed as dotted string. Cost: one full plan-checker → revision cycle (~50 min). **Fix for future:** when a plan touches an existing function signature, the planner should `<read_first>` the deployed file and quote the signature verbatim into the plan's `<interfaces>` block — not paraphrase from memory.
- **Plan 04-02 stream-idle timeout.** First spawn of the Phase 4 Wave 2 executor timed out at ~13 min with 24 tool uses and zero commits. Respawning with a streamlined "sample, don't read in full" file list completed the same work in ~10 min. **Pattern:** when a Task() agent has too many `<files_to_read>` entries, it spends its context on reading instead of writing. For executor agents in particular, give them a tight read list plus "sample signatures, don't read in full" for supporting files.
- **Stray `cd` in Phase 4 Wave 1 executor.** One Bash call used `cd skills/...` which landed a RED commit on main (`c7fe303`) before the agent's HEAD-assertion shifted to the worktree branch. The cherry-picked equivalent `a77ff9a` merged cleanly with no working-tree corruption, but the history shows two duplicate RED commits. Cosmetic, not destructive. **Fix:** executor agents must use absolute paths exclusively — `cd` is banned. Subsequent waves (2 + 3) avoided `cd` and stayed clean.
- **REQUIREMENTS.md checkbox sync drift.** The traceability checkboxes for CHUNK-*, INGEST-*, CITATION-* were stale (15 of 24 still `[ ]`) at audit time despite phases being complete. The milestone audit caught this. **Fix:** wire a hook into VERIFICATION.md generation that flips traceability checkboxes when a phase verifier passes — closes the loop automatically.

### Patterns Established

- **One file per source class** in `skills/patchbay-research/source_classes/<name>.py`, self-registering into `REGISTRY` via an idempotent tail snippet. Adding a fifth source class is a one-file, one-line-append operation.
- **`tier_used` is a first-class chunk field** — every chunk records which tier its data came from. Sweep-emitted chunks (synthetic) use `tier_used=None`, honestly signaling "this didn't come from a fetch."
- **Stable hash-based synthetic IDs** (e.g. `ext-sweep-{sha1(canonical_url)[:8]}`). Re-runs produce identical IDs for the same input. No monotonic counters that drift across runs.
- **`<read_first>` block in every task** lists the file being modified + any "source of truth" reference files. Executors read those before touching code.
- **`<acceptance_criteria>` is grep-verifiable.** No "looks correct" / "properly configured" — only exact strings, function signatures, command outputs.
- **Plan-checker → planner-revision loop is bounded at 3 iterations.** Phase 4 hit `## VERIFICATION PASSED` on iteration 2 after iteration 1 surfaced 4 BLOCKERs + 6 WARNINGs. The discipline keeps revisions targeted instead of replanning from scratch.

### Key Lessons

1. **Spike-validated architecture pays off twice** — once in execution speed (no schema changes mid-flight), once in audit speed (the audit cross-references against locked spike contracts).
2. **Interface drift is the #1 BLOCKER source in TDD plans.** The planner reads SUMMARY.md and the spike findings but doesn't always read the *deployed* code. Force it to via `<read_first>` whenever an existing function is modified.
3. **Worktree isolation is worth the merge overhead.** Three sequential merges + a stray-main-commit recovery still net out faster than debugging cross-plan contamination on a shared working tree.
4. **The verifier should be a separate agent, not the executor.** Executors have a self-evaluation blind spot — their `Self-Check: PASSED` is unreliable. A fresh-context verifier traces the call graph independently and catches what the executor missed.
5. **"Observable in terminal output, not buried in a log file"** is a *load-bearing UX rule*, not a nicety. Phase 4 Plan 02 enforces it: empty results still print a guidance line and exit 0; silent success is never allowed.

### Cost Observations

- **Model mix:** ~70% Opus (planner, plan-checker, verifier — high-stakes reasoning), ~30% Sonnet (executors — they follow plans, not generate them). Sonnet executors plus a strict plan + a strict verifier outperformed a single Opus monolith on this milestone.
- **Sessions:** 5-6 distinct work sessions for v2.0 (kickoff → Phase 2 → Phase 3 plans 1-5 → Phase 4 plan + execute + verify + audit + close).
- **Notable efficiency win:** chunked plan execution (each plan in its own worktree, atomic commit, separate executor) recovered cleanly from the Wave 1 stray-commit and Wave 2 stream-idle-timeout. No work was lost.
- **Notable cost surprise:** Phase 4 planning ate ~100 minutes total (initial plan ~50 min + revision after BLOCKERs ~50 min). The revision was the right call (fixes were targeted, not from-scratch) but the BLOCKERs themselves were avoidable with stricter `<read_first>` discipline.

## Cross-Milestone Trends

| Milestone | Phases | Plans | Tasks | Test Suite | Audit Status | Time-to-ship |
|-----------|--------|-------|-------|-----------|--------------|--------------|
| v1.0 dialed-in | 1 | 1 | — | (none) | — | ~1 session |
| v2.0 gear-knowledge | 3 | 8 | 17 | 138 pytest cases | TECH_DEBT (passed) | ~10 days, 5-6 sessions |

**Trends to watch:**
- v2.0's audit status (`tech_debt`, not `passed`) is fine for now but should not become a habit. The three non-blocking items (INGEST-03 live re-verify, CITATION-02 same-class under-count, duplicate RED commit) are all known and tracked, but the next milestone should aim for clean `passed`.
- Both shipped milestones used spike-driven architecture validation. The pattern is locked in.
- TDD adoption grew from "implicit" (v1.0) to "explicit RED/GREEN per task" (Phase 4 of v2.0). v3.0 should continue this.

---
*Last updated: 2026-05-18 after v2.0 (gear-knowledge) milestone.*
