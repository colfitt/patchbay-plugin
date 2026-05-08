# patchbay-plugin

## What This Is

Claude Code plugin for musicians. Inventory your gear, research tones, design patches, and chase the sounds behind the songs you love. Skills produce structured, searchable markdown files (SongProfiles, GearProfiles, dial-ins) that work in markdown today and are designed to render in a future visual interface.

## Core Value

Every artifact this plugin produces must remain a useful, source-cited markdown file in the user's local filesystem — searchable today, renderable as UI tomorrow.

## Current Milestone: v2.0 gear-knowledge

**Goal:** Build the gear-knowledge substrate so downstream skills (and the eventual conversational AI) can answer hover-citable questions about the user's gear.

**Target features:**
- `patchbay:ingest` — manual PDF → chunks via Claude's Read tool. Backbone of the per-gear knowledge store.
- `patchbay:research` — multi-source web ingest (Equipboard, Reddit, articles, YouTube) with tier-1 / 2 / 3 / 0 fetch ladder + structured `failures.log` for user-driven escalation.
- Chunk schema + per-gear knowledge store — the load-bearing data layer. Validated across 3 source classes in spikes 001-003c.
- Cross-source citation tracking — citation-count → "watch this" recommendations, plus artist↔gear graph edges.

**Architecture pre-validated by spikes 001 / 002a / 002c / 003 / 003b / 003c.** See [`spike-findings-patchbay-plugin`](../.claude/skills/spike-findings-patchbay-plugin/) skill for the full chunk schema, source-class blueprints, and constraints.

## Requirements

### Validated

- ✓ `liner-notes` skill — researches gear/tone behind a song and writes SongProfile.md with sourced gear breakdown and inventory-matched Applied section
- ✓ `dialed-in` skill — generate and save gear dial-in sessions as structured markdown files (knob positions, toggle states, signal chain context, technique notes) anchored to a specific song + gear substitution (shipped in milestone v1.0)
- ✓ Folder convention reference (`references/convention.md`) — defines paths, slug rules, `patchbay.yml` config
- ✓ Inventory reference (`references/inventory.md`) — owned-gear normalization
- ✓ Sources reference (`references/sources.md`) — per-site fetch strategies

### Active

- [ ] Chunk schema + per-gear knowledge store — the unified data layer all ingest skills serialize to (manual / YT / web)
- [ ] `patchbay:ingest` skill — full-fidelity manual PDF ingestion via Read tool, every image described
- [ ] `patchbay:research` skill — tiered web ingest (tier 1 static fetch / tier 2 Claude_in_Chrome / tier 3 computer-use+vision / tier 0 manual paste) with `failures.log` escalation flow
- [ ] Knowledge-graph chunk types — `artist_usage` (gear↔artist edges) and `cross_ref` (gear↔gear used_with / similar_in_category)
- [ ] Citation-count recommendations — when a YT video / article is referenced from N independent sources, surface to user as "worth verifying"

### Out of Scope (this milestone)

- **User taste profile** — independent of substrate; planned for a future milestone (seed: [user-taste-profile.md](seeds/user-taste-profile.md))
- **Conversational AI / hover-citation UX** — the consumer of this substrate, not part of building it
- **Whisper transcription for YouTube** — auto-captions are sufficient for v1 (validated spike 002a / 002c); Whisper is a quality upgrade for a future milestone
- **Tier-2 extension auto-install flow** — production should detect `[]` from `list_connected_browsers` and surface install hint, not auto-install
- **Bounding-box provenance** — `{source, location_anchor}` is sufficient for v1; bbox is v2+ concern

## Context

Plugin lives at `/Users/cfitt/Dev/patchbay-plugin`. Skills follow a single-file pattern: `skills/<skill-name>/SKILL.md` with frontmatter (`name`, `description`) plus markdown body. The existing `liner-notes` and `dialed-in` skills are the canonical reference for shape, conventions, and tone.

Songs are stored under `<songs_root>/<Artist>/<song-slug>/` (default `Songs/`). The `dialed-in` skill writes to `<song-folder>/dial-in/<owned-slug>--<target-slug>.md` with a parallel `dial-in/sources/` cache dir.

For the v2.0 milestone, gear knowledge is stored under `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` (one append-only chunk per JSON line, schema in [spike-findings-patchbay-plugin](../.claude/skills/spike-findings-patchbay-plugin/references/chunk-schema.md)).

Architecture is fully spec'd by spikes 001 (manual ingest validation), 002a/002c (YT ingest validation), and 003/003b/003c (tiered web ingest validation). The `spike-findings-patchbay-plugin` skill auto-loads in implementation work.

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
| Spike-driven architecture validation for v2.0 | Five spikes (001, 002a, 002c, 003, 003b, 003c) validated chunk schema across 3 source classes before committing to plan-phase | ✓ Good (skill: spike-findings-patchbay-plugin) |
| Cheap-by-default + user-driven escalation for web ingest | Tier 1 → log failures → user reviews → tier 2 (Claude_in_Chrome) or tier 3 (computer-use+vision). Tier 0 (paste) demoted to last-resort after spike 003b showed paste is incomplete | ✓ Good |
| YouTube is secondary, web articles primary | EB carries verbatim YT review text already (meta-aggregator); YT multimodal is a "good tool, not the best tool" per user's spike 002 verdict | ✓ Good |
| Defer user-taste profile | Independent of substrate; user explicitly chose to defer at milestone v2.0 kickoff | — Pending future milestone |

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
*Last updated: 2026-05-08 — milestone v2.0 (gear-knowledge) started*
