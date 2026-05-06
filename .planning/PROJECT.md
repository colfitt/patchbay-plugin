# patchbay-plugin

## What This Is

Claude Code plugin for musicians. Inventory your gear, research tones, design patches, and chase the sounds behind the songs you love. Skills produce structured, searchable markdown files (SongProfiles, GearProfiles, dial-ins) that work in markdown today and are designed to render in a future visual interface.

## Core Value

Every artifact this plugin produces must remain a useful, source-cited markdown file in the user's local filesystem — searchable today, renderable as UI tomorrow.

## Requirements

### Validated

- ✓ `liner-notes` skill — researches gear/tone behind a song and writes SongProfile.md with sourced gear breakdown and inventory-matched Applied section
- ✓ Folder convention reference (`references/convention.md`) — defines paths, slug rules, `patchbay.yml` config
- ✓ Inventory reference (`references/inventory.md`) — owned-gear normalization
- ✓ Sources reference (`references/sources.md`) — per-site fetch strategies

### Active

- [ ] `dialed-in` skill — generate and save gear dial-in sessions as structured markdown files (knob positions, toggle states, signal chain context, technique notes) anchored to a specific song + gear substitution

### Out of Scope (this milestone)

- Visual UI rendering of dial-ins — clock-position format is designed to support this later, but no UI work in this milestone
- Auto-generating dial-ins for songs without an existing SongProfile — `dialed-in` requires `liner-notes` to have run first
- Multi-song batch dial-in generation — single-song scope per invocation
- Audio plugin / DAW integration — markdown artifacts only

## Context

Plugin lives at `/Users/cfitt/Dev/patchbay-plugin`. Skills follow a single-file pattern: `skills/<skill-name>/SKILL.md` with frontmatter (`name`, `description`) plus markdown body. The existing `liner-notes` skill is the canonical reference for shape, conventions, and tone.

Songs are stored under `<songs_root>/<Artist>/<song-slug>/` (default `Songs/`). The `dialed-in` skill writes to `<song-folder>/dial-in/<owned-slug>--<target-slug>.md` with a parallel `dial-in/sources/` cache dir.

Design spec for this milestone: [docs/specs/2026-05-06-patchbay-dialed-in-design.md](../docs/specs/2026-05-06-patchbay-dialed-in-design.md). The spec is the source of truth for invocation patterns, the 8-step process, frontmatter schema, error handling, and UI layer notes.

## Constraints

- **Format**: Clock-position knob values (`2:00`, `9:00`) — load-bearing for future UI knob rendering. No format migration acceptable.
- **Routing**: `dialed-in` only runs when a SongProfile.md exists; otherwise returns a recoverable empty-state message pointing the user back to `liner-notes`.
- **Citation**: Source files cached under `dial-in/sources/<target-gear-slug>-<YYYY-MM-DD>.md`; 30-day cache window before re-fetch.
- **Idempotence**: Re-running on an existing dial-in surfaces a 4-option re-run menu (Refresh / Extend / Leave it / Start over), matching `liner-notes` precedent.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| One file per owned-gear/target-gear pair | Each file is a card in a future UI; filter by `owned_gear_slug` or `target_gear_slug` | — Pending |
| Clock-position knob format | Human-readable in markdown today, directly renderable as knob angle in UI | — Pending |
| `tags` in frontmatter | Full-text search across library by song, artist, gear — no separate index | — Pending |
| Skip GSD research phase | Spec is complete; no domain research needed for one skill file | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-06 after initialization*
