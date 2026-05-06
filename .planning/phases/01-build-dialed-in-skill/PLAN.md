# Phase 1 Plan — Build dialed-in skill

**Phase:** 1
**Goal:** Author `skills/dialed-in/SKILL.md` end-to-end, matching the design spec verbatim where the spec dictates exact text and matching the `liner-notes` skill pattern in shape and voice.

**Source spec:** [docs/specs/2026-05-06-patchbay-dialed-in-design.md](../../../docs/specs/2026-05-06-patchbay-dialed-in-design.md)
**Reference skill:** [skills/liner-notes/SKILL.md](../../../skills/liner-notes/SKILL.md)

---

## Workstream / parallelism decision

The roadmap noted two logical sub-streams (body sections vs tables). After review: this is a single markdown file (~250 lines) with shared voice, shared cross-references between sections (e.g. error-handling table references step numbers, UI notes reference frontmatter fields), and no test surface to parallelize against. The orchestration overhead and merge cost of running two agents would exceed the cost of writing it directly.

**Decision:** sequential, single-author. Workstreams not used for this phase. The spec is the parallelism — Claude has the full spec in context and can transcribe/adapt it in one pass.

If future skills in this plugin require multi-file deliverables (e.g. SKILL.md + reference docs + test fixtures), revisit workstreams then.

---

## Tasks

Each task is one atomic commit unit.

### T1 — Write SKILL.md

Create `skills/dialed-in/SKILL.md` with:

1. **Frontmatter** — `name: dialed-in`, `description:` covering all five trigger phrases (the four invocation patterns from spec § Invocation patterns + the `liner-notes` follow-up handoff)
2. **Intro paragraph + "Before starting" pointer** — match `liner-notes` shape; reference `references/convention.md`, `references/inventory.md`, `references/sources.md`
3. **Invocation patterns section** — list all four patterns as a code block (mirroring the spec) plus the liner-notes-follow-up note
4. **Process — 8 steps** — Step 1 through Step 8 from spec § Process. Preserve exact strings for:
   - "No liner notes found for [Song] by [Artist]. Run `liner-notes` first, then come back."
   - "No gear substitutions found in Applied. Check that your GearProfile slugs are correct or re-run `liner-notes`."
   - The Step 3 numbered substitution menu prompt
   - The Step 4 re-run menu (Refresh / Extend / Leave it / Start over)
   - The Step 8 "Want to continue with the remaining substitutions?" prompt
5. **Data model section** — file location tree, filename convention, frontmatter schema (yaml block), body structure (markdown block) — all verbatim from spec § Data model
6. **Error-handling table** — all 8 rows from spec § Error handling
7. **UI layer notes section** — full table from spec § UI layer notes plus the closing rationale ("Clock positions are the most load-bearing UI decision...")

### T2 — Verify SKILL.md against spec

Re-read SKILL.md against REQUIREMENTS.md checklist (SKILL-01..03, PROC-01..08, DATA-01..03, ERR-01..02, UI-01..02). Each requirement must have a clear locus in the file.

### T3 — Commit

Single commit: `feat: add skills/dialed-in/SKILL.md`. Includes only `skills/dialed-in/SKILL.md` — planning artifacts already committed separately.

---

## Out of scope for Phase 1

- No test harness for the skill (skills are validated at runtime by Claude)
- No example dial-in markdown files (those are user-generated artifacts)
- No `references/dial-in.md` reference doc (the spec is the design; if future runtime evidence shows we need a separate reference, that's a follow-up)
- No `marketplace.json` updates (the existing `source: ./` glob picks up new skills automatically)

## Verification

Phase succeeds when:

1. `skills/dialed-in/SKILL.md` exists, parses (valid YAML frontmatter, well-formed markdown body)
2. Every requirement in REQUIREMENTS.md `## v1 Requirements` has a corresponding section/passage in the SKILL
3. Error messages and menu prompts where the spec dictates exact strings appear verbatim
4. Section ordering and voice match `skills/liner-notes/SKILL.md`
