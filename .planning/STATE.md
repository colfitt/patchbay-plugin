---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: gear-knowledge
status: ready_to_plan
stopped_at: 03-05 Task 1 complete; awaiting human verification on Tasks 2a (extension-INDEPENDENT smoke) and 2b (extension-DEPENDENT tier-2 escalation, likely deferred)
last_updated: "2026-05-16T02:39:00.000Z"
last_activity: 2026-05-16
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 5
  completed_plans: 4
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-08)

**Core value:** Every artifact this plugin produces must remain a useful, source-cited markdown file in the user's local filesystem — searchable today, renderable as UI tomorrow.
**Current focus:** Phase 03 — patchbay:research with tiered fetch

## Current Position

Phase: 4
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-17

Progress: [████████░░] 80% — Plan 03-05 Task 1 done; phase-close gated on Task 2a approval

## Performance Metrics

**Velocity:**

- Total plans completed: 6 (v1.0 Phase 1)
- Average duration: — (single-plan milestone)
- Total execution time: —

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 (v1.0) | 1 | — | — |
| 03 | 5 | - | - |

**Recent Trend:**

- Last plan: Phase 2 / Plan 03 (verify) shipped 2026-05-12
- Trend: Phase 2 complete — patchbay-ingest skill verified end-to-end against real owned-gear manual

*Updated after each plan completion*
| Phase 03 P01 | 8min | 2 tasks | 9 files |
| Phase 03 P03-02 | 4min | 2 tasks | 5 files |
| Phase 03 P03-03 | 5min | 2 tasks | 5 files |
| Phase 03 P04 | 7min | 3 tasks | 8 files |
| Phase 03 P05 (Task 1 only) | 14min | 1 task (autonomous) | 5 files created + 1 modified (SKILL.md additive) |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v2.0 kickoff: Spike-driven architecture validation — six spikes (001, 002a, 002c, 003, 003b, 003c) locked the chunk schema, fetch-tier ladder, and source-class blueprints before plan-phase
- v2.0 kickoff: Cheap-by-default + user-driven escalation for web ingest (no auto-fallback between tiers)
- v2.0 kickoff: YouTube is secondary, web articles primary (Equipboard already carries verbatim YT review text)
- v2.0 kickoff: User-taste-profile deferred to a future milestone
- [Phase 03]: Self-registering source-class registry pattern — Plans 02/03/04 add one import line each; generic = REGISTRY[-1] — Keeps registry skeleton genuinely empty; commutative merges across Wave 2 plans
- [Phase 03]: Bidirectional name extraction for cross_source_match_candidates — Required because possessive variants (Rhett Shull's) don't substring-match the bare form; one-directional scan missed the test case
- [Phase 03]: update_chunk_field landed in Plan 01 (not Plan 04) — Plan 04 YouTube two-pass enrichment becomes a 4-line change instead of a 4-file change; load-bearing helper deserves to ship with its tests
- [Phase 03]: Self-registration idempotency guard — every source-class module wraps the REGISTRY append in 'if _self not in _REGISTRY' so importlib.reload cycles don't double-register
- [Phase 03]: Chunk IDs grounded on data.id (Reddit-assigned post id), not URL slug — slugs can be edited by mods; data.id is the stable join key for re-ingest diffs
- [Phase ?]: [Phase 03 Plan 03]: Two-pass emit pattern for citing_chunk_ids — any chunk type whose citing_chunk_ids references another chunk MUST emit AFTER the cited chunk. Plan 04 will hit this same constraint.
- [Phase ?]: [Phase 03 Plan 03]: VERBATIM_QUOTE_MIN_CHARS = 80 — short text collapses into summary; only text >= 80 chars becomes verbatim_quote, honoring RESEARCH-08 without inventing quotes.
- [Phase ?]: [Phase 03 Plan 03]: BeautifulSoup with html.parser (stdlib), NOT lxml — XXE/billion-laughs immune by parser choice (T-03-15/T-03-18).
- [Phase 03]: Plan 03-04: Two-pass YouTube enrichment via <<PENDING_READ_TOOL_DESCRIPTION>> sentinel + provenance.frame_path; SKILL driver Reads each frame and overwrites via write_chunk.update_chunk_field.
- [Phase 03]: Plan 03-04: Sentinel tier-1 fetch ({needs_pipeline: True}) for YouTube — SKILL driver dispatches parse_to_chunks directly, no static GET for /watch pages.
- [Phase 03]: Plan 03-04: VTT windows anchored to first cue start (not fixed grid) so deep_link timestamps stay surgically aligned with content.
- [Phase 03]: Plan 03-05: Dependency-injected MCP tools (`mcp_tools: Mapping[str, Callable]`) — review_failures / tier2_chrome / tier3_vision accept tool callables as parameters so the test suite can exercise the full dispatcher without a real Chrome extension, and the SKILL driver wires `mcp__*` callables at runtime. No MCP SDK runtime dep.
- [Phase 03]: Plan 03-05: Append-only resolution-record pattern — successful or failed escalations append a NEW JSON line; original failure entry NEVER rewritten. load_failures filters URLs whose latest record is a resolution. Preserves audit trail.
- [Phase 03]: Plan 03-05: REGISTRY-state guard at the dispatcher — review_failures detects when test-cycle reloads have emptied source_classes.REGISTRY and reloads the cached submodules so their self-registration tail re-fires. Mirrors Plan 02's idempotency guard at the consumer level (instead of fixing four upstream test files).
- [Phase 03]: Plan 03-05: tier_used stamping in `_parse_and_write` — every chunk gets `chunk['tier_used'] = fetch_result['tier']` before write_chunks. Defensive against parsers that hardcode tier_used=1 (Plan 04 youtube). Guarantees a tier-2 escalation records tier_used=2 in chunks.jsonl, never silently downgrades to 1.

### Pending Todos

- **Multi-batch boundary verification (INGEST-03 deferral)** — re-verify on first ingest of a >20-page manual (candidates in Pedalxly inventory: Akai MPC Sample, Strymon TimeLine, Roland VG-800, Eventide H90). Tracked in `docs/verify/02-chunk-schema-and-patchbay-ingest.md` § Multi-batch boundary test.
- **Phase 2 findings (4) for future spikes / Phase 2.1 if needed:**
  1. Foldout-poster manuals violate the "1–4 chunks/page" rule wording — rule needs revision (substance is correct).
  2. SKILL.md should explicitly require a real JSON encoder for chunk writing (`json.dumps`/`JSON.stringify`) — raw `\n` in strings breaks RFC 8259.
  3. State-transition tables are a real edge case for the 7-category enum — candidate eighth category (`state-diagram`) for a future spike.
  4. Pedalxly's top-level `Manuals/` folder is unused; future `add-gear`/`soundcheck` could route from there into gear folders.

### Blockers/Concerns

**Open obligation: RESEARCH-05 production proof (Task 2b of Plan 03-05).** Plan 05 Task 1's automated tests fully cover the Chrome-extension precheck path (empty `list_connected_browsers` → install instructions + extension-missing resolution + NO auto-fallback). However the production proof — a real `--review-failures` run that escalates an Equipboard URL to tier 2 via the actual Claude_in_Chrome MCP and writes chunks with `tier_used=2` — is gated on Task 2b's checkpoint. The MCP is NOT available in the current execution session, so 2b is expected to be marked `status: extension-deferred` (NOT approved). RESEARCH-05 is NOT marked complete until Task 2b's extension-installed path is observed. The user can satisfy this later by installing the Claude in Chrome browser extension and re-running the `--review-failures` flow against a fresh Equipboard failure.

**Phase-close gate: Task 2a of Plan 03-05.** Phase 3 cannot close until Task 2a (extension-INDEPENDENT smoke run: tier-1 Reddit success + Equipboard tier-1 failure + `--review-failures` listing + paste-manually tier-0 ingestion + cross_source_match_candidates emergence) is approved by the user.

Architecture is otherwise heavily pre-validated by spike findings; the `spike-findings-patchbay-plugin` skill auto-loads in implementation work.

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Substrate-adjacent | User taste profile | Deferred | v2.0 kickoff |
| YouTube quality | Whisper transcription | Deferred | v2.0 kickoff |
| Provenance | Bounding-box provenance | Deferred (v2+) | v2.0 kickoff |
| Setup UX | Tier-2 extension auto-install | Deferred | v2.0 kickoff |
| Consumer UX | Conversational AI / hover-citation UX | Deferred (separate milestone) | v2.0 kickoff |

## Session Continuity

Last session: 2026-05-16T02:39:00.000Z
Stopped at: 03-05 Task 1 complete; Tasks 2a (extension-INDEPENDENT, MUST pass) and 2b (extension-DEPENDENT, deferred-OK) awaiting human verification
Resume file: .planning/phases/03-patchbay-research-with-tiered-fetch/03-05-SUMMARY.md (Tasks 2a/2b status section)
