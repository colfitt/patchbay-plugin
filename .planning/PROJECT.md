# patchbay-plugin

## What This Is

Claude Code plugin for musicians. Inventory your gear, research tones, design patches, and chase the sounds behind the songs you love. Skills produce structured, searchable markdown files (SongProfiles, GearProfiles, dial-ins) that work in markdown today and are designed to render in a future visual interface.

As of v2.0, every gear-related skill writes into a unified per-gear knowledge store at `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` — append-only, schema-validated, citation-ready. The substrate is built; v3.0+ skills consume it.

## Core Value

Every artifact this plugin produces must remain a useful, source-cited markdown file in the user's local filesystem — searchable today, renderable as UI tomorrow.

## Current State

**Shipped:** v1.0 (dialed-in skill, 2026-05-07) + v2.0 (gear-knowledge substrate, 2026-05-18).

**v2.0 delivered:**
- `patchbay:ingest` — manual PDF → schema-valid chunks.jsonl
- `patchbay:research <gear>` — tiered web ingest (Equipboard, Reddit, articles, YouTube) into the same chunks.jsonl
- `patchbay:research --review-failures` — interactive escalation (tier 2 / tier 3 / paste / skip), no auto-fallback
- `patchbay:research --citations <gear>` — surface URLs referenced by N distinct sources
- `patchbay:research --verify <gear> <url>` — mark a recommendation verified → ingest + promote to high-trust
- 138 pytest cases green; 24/24 v2.0 requirements satisfied; goal-backward verification + integration check both passed

**Next milestone goals (v3.0, draft):**
- Skill rename: `liner-notes` → `tone-chase` (cosmetic; prerequisite for the conversational skill). Across SKILL.md, plugin.json, CLAUDE.md routing.
- **`patchbay:finish-a-damn-song`** — conversational pre-production partner driven by **ARLO**. Design committed: [`docs/specs/2026-05-18-patchbay-finish-a-damn-song-design.md`](../docs/specs/2026-05-18-patchbay-finish-a-damn-song-design.md). Four optional flags (`--producer`, `--engineer`, `--editor`, `--guy-in-the-chair`), per-song `ARLO.md` journal, Socratic-only lyric editing (no generation), `--gas` rename from `--gas-mode`.
- Other candidates ordered in [`ROADMAP.md`](ROADMAP.md): `patchbay:midi`, `patchbay:soundcheck`, `patchbay:add-gear`, hover-citation UX, CITATION-02 primary-source independence, multi-gear tone-graph queries, `patchbay:purge`.

## Requirements

### Validated

- ✓ `liner-notes` skill — SongProfile.md with sourced gear breakdown and inventory-matched Applied section (v1.0)
- ✓ `dialed-in` skill — dial-in sessions as structured markdown anchored to song + gear substitution (v1.0)
- ✓ Folder convention reference (`references/convention.md`) — paths, slug rules, `patchbay.yml` config (v1.0)
- ✓ Inventory reference (`references/inventory.md`) — owned-gear normalization (v1.0)
- ✓ Sources reference (`references/sources.md`) — per-site fetch strategies (v1.0)
- ✓ Chunk schema + per-gear knowledge store (`<gear_root>/<Brand Item>/knowledge/chunks.jsonl`) — unified data layer (v2.0)
- ✓ `patchbay:ingest` skill — full-fidelity manual PDF ingestion, every image described (v2.0)
- ✓ `patchbay:research` skill — tiered web ingest with `failures.log` escalation flow (v2.0)
- ✓ Knowledge-graph chunk types — `artist_usage` + `cross_ref` (used_with / similar_in_category) (v2.0)
- ✓ Citation-count recommendations — `--citations` surface + `--verify` promotion to high-trust (v2.0)

### Active

(none yet — set at `/gsd-new-milestone` for v3.0)

### Out of Scope (this project)

- **Whisper transcription for YouTube** — auto-captions are sufficient (validated spike 002a / 002c); Whisper is a quality upgrade not worth the dependency.
- **Tier-2 extension auto-install flow** — production detects `[]` from `list_connected_browsers` and surfaces install hint; no auto-install.
- **Bounding-box provenance** — `{source, location_anchor}` is sufficient; bbox is a future precision upgrade.

### Out of Scope (deferred to a future milestone)

- **User taste profile** — independent of substrate (seed: [user-taste-profile.md](seeds/user-taste-profile.md)).
- **CITATION-02 primary-source independence** — current implementation counts distinct `source` fields on citing chunks; same-class re-publication under-counts. Tracked in `must_haves.known_limitations` of 04-02 + `references/citations-flow.md`.
- **INGEST-03 multi-page batch re-verify** — code path is exercised in unit tests; live re-verify deferred until first ingest of a >20-page manual.
- **RESEARCH-05 production proof (Task 2b)** — Chrome-extension tier-2 escalation test is gated on Claude_in_Chrome MCP availability; deferred-OK per Phase 3 close.

## Context

Plugin lives at `/Users/cfitt/Dev/patchbay-plugin`. Skills follow `skills/<skill-name>/SKILL.md` with frontmatter (`name`, `description`) plus markdown body. After v2.0, `patchbay:ingest` and `patchbay:research` ship Python script support modules under `skills/<skill>/scripts/` with their own pytest suites.

**Tech stack:** Markdown skills + Python 3 helpers (no external runtime deps beyond stdlib, `requests`, `BeautifulSoup` for tier-1 fetch, `yt-dlp` + `ffmpeg` for YouTube). Tests via pytest. The shipped chunk schema is locked in `.claude/skills/spike-findings-patchbay-plugin/references/chunk-schema.md`.

**Storage layout:**
- Songs: `<songs_root>/<Artist>/<song-slug>/` (default `Songs/`)
- Dial-ins: `<song-folder>/dial-in/<owned-slug>--<target-slug>.md` with `dial-in/sources/` cache
- Gear knowledge: `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` (append-only) + `failures.log` (append-only)

**Architecture validated by spikes 001 / 002a / 002c / 003 / 003b / 003c.** The `spike-findings-patchbay-plugin` skill auto-loads in implementation work.

**LOC (skills/ after v2.0):** ~10.9k lines (Python + Markdown). 138 pytest cases on `patchbay-research`.

## Constraints

- **Format**: Clock-position knob values (`2:00`, `9:00`) — load-bearing for future UI knob rendering. No format migration acceptable.
- **Routing**: `dialed-in` only runs when a SongProfile.md exists; otherwise returns a recoverable empty-state message pointing the user back to `liner-notes` (renaming to `tone-chase` in v3.0).
- **Citation**: Source files cached under `dial-in/sources/<target-gear-slug>-<YYYY-MM-DD>.md`; 30-day cache window before re-fetch.
- **Idempotence**: Re-running on an existing dial-in surfaces a 4-option re-run menu (Refresh / Extend / Leave it / Start over).
- **Chunk schema** (v2.0+): additive only — new fields fine, no breaking renames or removals. All chunks must carry `id`, `type`, `source`, `content`, `provenance`.
- **No auto-fallback between fetch tiers** — every escalation is user-driven via `--review-failures`.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| One file per owned-gear/target-gear pair | Each file is a card in a future UI; filter by `owned_gear_slug` or `target_gear_slug` | ✓ Good (v1.0 shipped, holding up) |
| Clock-position knob format | Human-readable in markdown today, directly renderable as knob angle in UI | ✓ Good |
| `tags` in frontmatter | Full-text search across library by song, artist, gear — no separate index | ✓ Good |
| Skip GSD research phase for v1.0 single skill | Spec was complete; no domain research needed | ✓ Good |
| Spike-driven architecture validation for v2.0 | Six spikes (001, 002a, 002c, 003, 003b, 003c) validated chunk schema across 3 source classes before plan-phase | ✓ Good (no schema changes needed during execution) |
| Cheap-by-default + user-driven escalation for web ingest | Tier 1 → log failures → user reviews → tier 2 (Claude_in_Chrome) or tier 3 (computer-use+vision). Tier 0 (paste) demoted to last-resort after spike 003b showed paste is incomplete | ✓ Good |
| YouTube is secondary, web articles primary | EB carries verbatim YT review text already; YT multimodal is a "good tool, not the best tool" per user's spike 002 verdict | ✓ Good (validated in production — `--citations` recommends YT URLs cited by multiple text sources) |
| Defer user-taste profile | Independent of substrate; chosen at v2.0 kickoff | — Pending future milestone |
| Self-registering source-class registry pattern | Plans 02-04 of Phase 3 add one import line each; generic dispatch = `REGISTRY[-1]` | ✓ Good (commutative merges across Wave 2; no merge conflicts) |
| Bidirectional name extraction for cross-source corroboration | Possessive variants ("Rhett Shull's") don't substring-match the bare form; one-directional scan missed test case | ✓ Good |
| `update_chunk_field` landed in Phase 3 Plan 01, not Phase 4 | Plan 04 YouTube two-pass enrichment becomes a 4-line change instead of a 4-file change | ✓ Good |
| BeautifulSoup with `html.parser` (stdlib), NOT lxml | XXE/billion-laughs immune by parser choice (T-03-15/T-03-18) | ✓ Good |
| VERBATIM_QUOTE_MIN_CHARS = 80 | Short text collapses into summary; only ≥80 chars becomes `verbatim_quote`, honoring RESEARCH-08 without inventing quotes | ✓ Good |
| Two-pass emit pattern for `citing_chunk_ids` | Any chunk type whose citing_chunk_ids references another chunk MUST emit AFTER the cited chunk | ✓ Good (Plan 04 hit this constraint as predicted) |
| Sweep at `write_chunks` writer boundary (Phase 4) | All source classes inherit CITATION-01 + CITATION-04 for free; no per-parser changes needed | ✓ Good |
| Stable hash-based sweep IDs (`ext-sweep-{sha1[:8]}`) | Re-runs produce identical IDs for the same canonical URL; no monotonic-counter collisions | ✓ Good |
| Distinct-source threshold key = citing chunk's `source` field | Cheap to compute, no extra schema field. Same-class re-publication under-counting is a known limitation deferred to a future phase | ✓ Good (v2.0); — Pending v3.x for primary-source tracking |
| `tier_used = null` for sweep-emitted chunks | Sweep is a synthetic derivation, not a fetch — preserves Phase 3's `tier_used` audit trail honestly | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with milestone reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-18 — v3.0 direction set: `finish-a-damn-song` (ARLO) spec'd; `liner-notes` → `tone-chase` rename queued as prereq*
