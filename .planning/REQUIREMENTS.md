# Requirements — patchbay `dialed-in` milestone

Source: [docs/specs/2026-05-06-patchbay-dialed-in-design.md](../docs/specs/2026-05-06-patchbay-dialed-in-design.md)

## v1 Requirements

### Skill scaffold

- [ ] **SKILL-01**: `skills/dialed-in/SKILL.md` exists with valid frontmatter (`name: dialed-in`, descriptive `description` triggering on dial-in language and `/dial-in` slash command)
- [ ] **SKILL-02**: SKILL body opens with a "Before starting" pointer to the three references (`convention.md`, `inventory.md`, `sources.md`), matching `liner-notes` precedent
- [ ] **SKILL-03**: Invocation patterns section lists the four documented patterns ("Dial in [song]…", "Dial in my [gear] for…", "Dial in my [gear] for the [role] in…", "/dial-in [query]") plus the liner-notes follow-up handoff

### Process — 8 steps

- [ ] **PROC-01**: Step 1 (Resolve target) — load SongProfile.md, error message exact when missing, skip file read when invoked as liner-notes follow-up
- [ ] **PROC-02**: Step 2 (Load substitutions) — parse `## Applied`, present numbered list, error message exact when empty
- [ ] **PROC-03**: Step 3 (Select gear) — direct path when user named gear; numbered menu (with multi-select syntax `1,3` or `all`) otherwise
- [ ] **PROC-04**: Step 4 (Existing-file check) — re-run menu offers Refresh / Extend / Leave it / Start over
- [ ] **PROC-05**: Step 5 (Research) — read owned GearProfile.md, fall back to WebSearch for control topology when GearProfile lacks a control map; check + populate `dial-in/sources/<target-gear-slug>-<YYYY-MM-DD>.md` with 30-day cache window; pull characteristics from SongProfile `## Research`
- [ ] **PROC-06**: Step 6 (Generate dial-in) — toggles before knobs; clock-position format for every knob; signal-chain context when role involves amp/interface; technique notes when sources mention them; 2–3 fine-tuning lines
- [ ] **PROC-07**: Step 7 (Write file) — create `dial-in/` if missing; filename `<owned-slug>--<target-slug>.md`; full frontmatter per schema
- [ ] **PROC-08**: Step 8 (Offer remaining) — list undialed substitutions, accept number/multi/`all`/`done`; suggest commit message when all done

### Data model

- [ ] **DATA-01**: Frontmatter schema documented in SKILL with all required fields (`type`, `song`, `artist`, `song_slug`, `artist_slug`, `date`, `owned_gear`, `owned_gear_slug`, `target_gear`, `target_gear_slug`, `role`, `confidence`, `sources`, `tags`)
- [ ] **DATA-02**: Body structure documented (Toggles table → Knobs section → Signal Chain → Technique → Fine-tuning → Sources)
- [ ] **DATA-03**: Filename convention `<owned-gear-slug>--<target-gear-slug>.md` (double-dash separator) called out explicitly with examples

### Error handling

- [ ] **ERR-01**: Error-handling table covers all 8 spec rows (no SongProfile, empty Applied, owned gear not in inventory, target controls unknown, file exists, no research sources, multi-player song, amp not in inventory)
- [ ] **ERR-02**: Each error row has the spec's exact behavior (stop / proceed-with-fallback / character-based guide / re-run menu / etc.)

### UI layer notes

- [ ] **UI-01**: SKILL preserves the spec's UI layer notes table and the "clock positions are the most load-bearing UI decision" callout
- [ ] **UI-02**: All format decisions in SKILL match the spec's UI rationale (clock positions, owned/target slugs, role field, tags array, confidence field)

## v2 / Out of Scope

- Audio playback or DSP integration
- Cross-song batch dial-in generation
- Auto-rendering knob diagrams in markdown (clock-position format reserved for future UI)
- Linting/validation tooling for dial-in markdown files

## Traceability

Filled by ROADMAP.md.
