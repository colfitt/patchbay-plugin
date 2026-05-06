# Roadmap — patchbay `dialed-in` milestone

**Milestone:** Ship the `dialed-in` skill so users can save and re-use gear dial-in sessions tied to specific songs and substitutions.

**Source spec:** [docs/specs/2026-05-06-patchbay-dialed-in-design.md](../docs/specs/2026-05-06-patchbay-dialed-in-design.md)

## Phases

| # | Phase | Goal | Requirements | UI hint |
|---|-------|------|--------------|---------|
| 1 | Build dialed-in skill | Author `skills/dialed-in/SKILL.md` end-to-end (frontmatter + 8-step process + data model + error handling + UI layer notes) so the skill activates and runs against the documented invocation patterns | SKILL-01..03, PROC-01..08, DATA-01..03, ERR-01..02, UI-01..02 | no (skill is markdown only; UI rendering reserved for a later milestone) |

## Phase 1 — Build dialed-in skill

**Goal:** A complete, valid `skills/dialed-in/SKILL.md` that matches every section of the design spec and follows the established `liner-notes` skill pattern.

**Requirements covered:** SKILL-01, SKILL-02, SKILL-03, PROC-01, PROC-02, PROC-03, PROC-04, PROC-05, PROC-06, PROC-07, PROC-08, DATA-01, DATA-02, DATA-03, ERR-01, ERR-02, UI-01, UI-02 (all v1 requirements).

### Success criteria

1. `skills/dialed-in/SKILL.md` exists, parses as valid frontmatter + body, and is discoverable as `patchbay:dialed-in` when the plugin is loaded.
2. SKILL covers all 8 process steps with the spec's exact prompts, menus, and error messages (verbatim where the spec dictates exact strings).
3. Frontmatter schema, filename convention, and body structure match the data-model section of the spec — every required field present, examples included.
4. Error-handling table reproduces all 8 spec rows with their stated behavior.
5. UI layer notes (clock-position rationale, owned/target slug filtering, etc.) are preserved verbatim from the spec — these are load-bearing for the future UI.
6. Style and shape mirror `skills/liner-notes/SKILL.md` (section ordering, voice, "Before starting" reference pointer, re-run menu language).

### Build approach

Single-file deliverable. Two parallelizable sub-streams during execution:

- **Stream A — Body sections (process + data model):** steps 1–8, frontmatter schema, body structure, filename convention.
- **Stream B — Tables (error handling + UI layer notes):** 8-row error table and UI layer notes table with closing rationale.

Streams converge into one `SKILL.md` file. Final stream merges and verifies.

## Coverage

All v1 requirements from REQUIREMENTS.md map to Phase 1. No requirements are unmapped.

## Out of milestone

- Visual UI rendering (deferred — a separate future milestone)
- Audio integration (out of scope)
- Multi-song batch dial-in (out of scope)
- Auto-generating without a SongProfile (out of scope — `dialed-in` requires `liner-notes` first)

---
*Last updated: 2026-05-06 after roadmap creation*
