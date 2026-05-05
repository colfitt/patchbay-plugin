# Design: `patchbay:liner-notes`

_Date: 2026-05-05 · Status: design complete, awaiting user review_

## Summary

`patchbay:liner-notes` is the song- and artist-tone research skill in the `patchbay` Claude plugin. A musician asks Claude *"Liner notes on Creep by Radiohead"* and gets back a markdown launchpad: documented gear used on the recording (with sources cited), a substitution-aware signal chain rendered against their own inventory, and a list of conversational next steps. It's designed to help musicians **either** prevent GAS by leaning on what they already own **or**, with GAS mode on, surface honest acquisition options including funded swaps from a sell list.

This skill writes the foundational research artifact; companion skills (`patchbay:dial-in`, `patchbay:purge`) handle deep patch design and inventory pruning.

## North star

> *"Help, or prevent GAS, by using what they already own."*

Default mode optimizes for substitution. GAS mode flips the posture to acquisition + replacement. The skill respects both — neither is the "right" answer.

## Plugin context

`patchbay` is a Claude plugin for musicians' personal studio knowledge bases. It's project-agnostic: detects existing folder conventions (e.g. Pedalxly's `Gear/<Brand Item>/`) or scaffolds a sensible default via `patchbay:soundcheck`. A per-project `patchbay.yml` captures paths and overrides.

Skills in the plugin (this spec only covers `liner-notes`):
- `patchbay:soundcheck` — first-time setup
- `patchbay:add-gear` — onboard gear
- `patchbay:purge` — review for sell candidates
- `patchbay:ingest` — pull a manual / article / video / book
- `patchbay:research` — deep gear or technique research
- **`patchbay:liner-notes`** — this skill
- `patchbay:dial-in` — patch design + recall
- `patchbay:midi` — `.mid` / `.syx` / real-time MIDI

Skills compose through the filesystem only. No direct skill-to-skill calls.

## Architecture & dependencies

| Depends on | Role | Owner |
|---|---|---|
| `references/inventory.md` | Read user's owned gear/software in normalized form | Plugin-level |
| `references/convention.md` | Detect project folder shape | Plugin-level |
| `references/sources.md` | Per-site fetch strategies | Plugin-level (shared with `patchbay:research`) |
| `add-youtube` Rust CLI | Pull rig-rundown video transcripts | External (`rust-tools/`) |
| `WebSearch` + `WebFetch` | Find and read articles | Claude built-in |

Sibling skills it composes with via filesystem:
- `patchbay:dial-in` writes patch files to `Songs/<Artist>/<song-slug>/patches/` on conversational request.
- `patchbay:add-gear` produces the inventory that `inventory.md` reads.
- `patchbay:purge` produces `Purge.md`, which GAS-mode acquisition reads to suggest funded swaps.

## Inputs & invocation

**Primary: conversational.** The skill activates on patterns like *"liner notes on X"*, *"research the gear behind Y"*, *"tell me what was used on Z"*.

**Optional secondary: slash command** `/song <query>` for keyboard quickness; same code path.

| Input | Behavior |
|---|---|
| Song title alone | Disambiguation prompt with year + genre. |
| Song + artist | Direct lookup. |
| Album track ref ("track 3 of OK Computer") | Resolves to song. |
| Artist alone ("the Bonham drum sound") | Routes to `Artists/<Artist>/ArtistProfile.md` flow (broader scope, rig over time). |
| GAS toggle phrase ("...with GAS on") | Per-call override of `patchbay.yml`. |
| Refresh phrase | Triggers re-run flow. |

### Disambiguation

Ambiguous title → Claude lists candidates with year + genre context, asks user to pick.

### Re-run flow

If `SongProfile.md` already exists, Claude offers four options:
- **Refresh** — re-fetch existing sources, update findings; existing `## Corrections` block preserved verbatim.
- **Extend** — keep existing `## Research`; append new angles (additional sources, related gear, deeper sub-instrument breakdowns).
- **Leave it** — abort.
- **Start over** — read existing `## Corrections` into memory, wipe the file, re-run from scratch, append the corrections block back at the end. Findings overridden by corrections re-apply automatically because `## Applied` reads both.

In all paths, **corrections are sacred**: re-running never deletes or alters user-authored corrections. If the user wants to clear corrections, they edit the file directly.

### GAS-mode resolution at call time

1. Per-call enable → on.
2. Per-call disable → off.
3. Otherwise read `patchbay.yml` `gas_mode` (default off).

## Process / data flow

1. **Resolve target.** Disambiguate if needed → `{artist, song, year, slug}`.
2. **Existing-file check.** If `SongProfile.md` exists, run re-run flow.
3. **Gather research** per `references/sources.md`:
   - Equipboard — direct fetch; web-search fallback if blocked.
   - Premier Guitar — search "creep radiohead rig rundown"; `WebFetch`.
   - Sound on Sound — same.
   - YouTube — search rig rundowns; `add-youtube` on top hits.
   - General web — `WebSearch` catch-all.
   - Each fetch saved raw to `sources/<site>-<YYYY-MM-DD>.md` with URL + `fetched_at` frontmatter.
4. **Synthesize `## Research`** — per-instrument breakdown with role, gear, confidence (high/med/low), citation refs. Conflicting sources surfaced explicitly: *"Equipboard says X, PG says Y."*
5. **Cross-reference inventory.** Plugin-level adapter returns owned gear; per-claim match: exact / same-category / generic.
6. **Build `## Applied`.** Prose signal chain using inventory matches + generic substitutions. Plus `## Where next` follow-up list.
7. **Build `## Gear Acquisition`** — see *Output* section for full logic.
8. **Apply corrections** (re-run only). Existing corrections re-applied as overrides.
9. **Atomic write** of `SongProfile.md`. Frontmatter updated. Suggest a git commit message.

**Citation rule:** every gear claim in `## Research` must reference a `sources/` file. No bare claims.

**Conflict handling:** when sources disagree, surface the conflict; don't pick a winner; let the user resolve via `## Corrections`.

## Outputs / file shape

**Folder per song:**

```
Songs/Radiohead/creep/
  SongProfile.md
  sources/
    equipboard-2026-05-05.md
    premier-guitar-2026-05-05.md
    youtube-rig-rundown-7Aw1J3lq.md
    web-2026-05-05.md
  patches/
    clean-verse.md     # written by dial-in on follow-up request
    crunchy-chorus.md
```

**`SongProfile.md`:**

```markdown
---
artist: Radiohead
song: Creep
slug: creep
year: 1992
album: Pablo Honey
key: G major
bpm: 92
genres: [alt-rock, grunge]
last_researched: 2026-05-05
last_corrected: null
gas_mode: false
sources:
  - equipboard-2026-05-05.md
  - premier-guitar-2026-05-05.md
  - youtube-rig-rundown-7Aw1J3lq.md
gear_referenced:
  - radiohead/jonny-greenwood/fender-telecaster
  - radiohead/jonny-greenwood/marshall-shredmaster
  - radiohead/jonny-greenwood/digitech-whammy-iv
---

# Creep — Radiohead

## Research
### Lead guitar (Jonny Greenwood)
- **Guitar:** Fender Telecaster Plus (high — Equipboard, PG)
- **Amp:** Marshall ShredMaster (high — PG-2026-05-05.md)
- **Pedal:** DigiTech Whammy II → IV (conflict; see Corrections)
- Signal chain: Tele → ShredMaster → amp; Whammy on chorus only.

### Rhythm guitar (Ed O'Brien)
…

### Vocals (Thom Yorke)
…

### Sources
- [equipboard-2026-05-05.md](sources/equipboard-2026-05-05.md)
- [premier-guitar-2026-05-05.md](sources/premier-guitar-2026-05-05.md)
- [youtube-rig-rundown-7Aw1J3lq.md](sources/youtube-rig-rundown-7Aw1J3lq.md)

## Applied
You own a Fender Player Telecaster (matches lead) and a JHS Pulp 'N Peel
(close to ShredMaster's mid-bite). No Whammy; closest is your EHX Pitch Fork
(octave-up mode covers the chorus pitch jumps).

Signal chain: guitar → Pitch Fork (chorus only, octave up, blend ~70%) →
Pulp 'N Peel (drive ~6, tone ~5, comp on) → amp (clean, slight breakup at master).

## Where next
- *Dial me settings for the Pitch Fork and Pulp 'N Peel using what I own.*
- *Cover-friendly version using just the pedalboard.*
- *Riff off this — what if I swap the Pitch Fork for a slow harmonizer setting?*

## Corrections
<!-- empty until user supplies -->

## Gear Acquisition
<!-- behavior depends on GAS state and inventory gap; see below -->
```

**`## Gear Acquisition` rendering logic:**

| GAS mode | Inventory covers it | Render |
|---|---|---|
| Off | Yes | Section omitted entirely. |
| Off | No (real gap) | One-line nudge: *"GAS mode is off. To fully match this sound you'd need a tape echo and a fuzz you don't currently own. Toggle GAS on for specifics."* A "real gap" means at least one gear category from `## Research` has no owned match — exact or category-level — that meaningfully affects the sound. Cosmetic differences (a slightly different fuzz model when the user owns one) don't trigger the nudge. |
| On | — | Funded swaps (read from `Purge.md`) + standalone acquisitions + wishlist additions, with reasoning per item. |

**`sources/<site>-<YYYY-MM-DD>.md`:**

```markdown
---
url: https://equipboard.com/pros/jonny-greenwood
fetched_at: 2026-05-05T14:23:00Z
fetcher: equipboard-direct
---

[clean readability output]
```

**Frontmatter conventions:**
- `gear_referenced` uses path slugs that resolve to user's `Gear/` folder when present.
- `last_researched` / `last_corrected` enable freshness UI later.
- `gas_mode: true` recorded only when GAS was on for the most recent run.

## Failure modes

| Failure | Behavior |
|---|---|
| Disambiguation impossible | 1–2 clarifying questions; if still unclear, refuse gracefully. |
| No sources found | Minimal `SongProfile.md` with a note to ingest user-supplied material and re-run. **No fabricated gear claims, ever.** |
| Equipboard / specific site blocks | Web-search fallback; failure logged inline so user sees what they got. |
| Inventory adapter finds nothing | `## Applied` renders with generic substitutions; header note recommends `soundcheck` + `add-gear`. |
| Re-run on corrupted `SongProfile.md` | Refuse to overwrite; propose backup-and-rewrite flow. **Never silently destroy user data.** |
| `add-youtube` CLI not installed | Skip YouTube sources; note in `## Sources`; recommend install. |
| `WebFetch` returns garbage | Skip that source; note inline; don't poison synthesis. |
| Correction conflicts with new finding | Correction wins; new finding logged with override note. |
| GAS requested but `Purge.md` missing | Standalone acquisitions only; recommend `patchbay:purge`. |
| Artist-only request | Routes to `Artists/<Artist>/ArtistProfile.md` flow (broader scope). |
| No-gear-relevant query (DJ tracks, sample-based hip-hop) | Detect from research; reframe: *"This track is sample-based — there isn't a traditional rig. Want me to research the samples used instead?"* |
| Found-object percussion query (pots and pans, rubber spatula on a counter) | Treat seriously — these are real production techniques (Björk, Tom Waits, Stomp). Note them in `## Research` as found-objects with technique notes; `## Applied` suggests household stand-ins; `## Gear Acquisition` typically empty. |

## Testing

Skills aren't traditional code; testing is rehearsal, not unit tests.

1. **Golden test cases** — small library of known-tone songs:
   - Creep — Radiohead (Whammy, ShredMaster)
   - Black Hole Sun — Soundgarden (Leslie cab, baritone fuzz)
   - One More Time — Daft Punk (sample + filter)
   - When the Levee Breaks — Led Zeppelin (room mic'd drums)
   - Smells Like Teen Spirit — Nirvana (heavily-documented chain)
2. **Edge-case prompts** — script exercising each failure mode. Quarterly rehearsal.
3. **Inventory variations** — three test inventories (rich Pedalxly-shaped, partial, empty). Same song against each. Validate `## Applied` adapts.
4. **GAS toggle parity** — same song, GAS on vs off, side-by-side.
5. **No automated tests in v1.** Add automated golden-output diffs only if drift becomes a real problem.

## Implementation prerequisites

This skill depends on plugin-level pieces that don't exist yet (`references/inventory.md`, `references/convention.md`, `references/sources.md`, `patchbay.yml` schema). Two valid implementation paths:

1. **Plugin-spec first** — write a separate plugin-level design spec resolving the deferred questions below, implement those pieces, then implement this skill. Cleaner architecture, slower to first usable output.
2. **Vertical slice** — implement minimum viable versions of the plugin-level pieces *as part of* implementing this skill. Faster to a usable result; the plugin-level pieces evolve as more skills get added.

The implementation plan (next phase) decides between these.

## Open questions deferred to plugin-level spec

- **`patchbay.yml` schema** — full field list and defaults. Belongs in the plugin spec, not this skill.
- **Inventory adapter API** — exact normalized shape returned to skills. Belongs in the plugin spec.
- **Source-fetch retry / caching policy** — how long to trust an existing `sources/` file before refetching. Default: trust until refresh.
- **MIDI helper boundary** — irrelevant for this skill but lives in the plugin spec.
- **Plugin distribution / install** — out of scope here.

These get resolved when the plugin-level spec is written. `liner-notes` consumes whatever shapes those produce.

## Out of scope

- Patch generation (handled by `patchbay:dial-in` on follow-up).
- Inventory onboarding (handled by `patchbay:add-gear`).
- Sell-list curation (handled by `patchbay:purge`).
- Real-time MIDI to gear (handled by `patchbay:midi`).
- Building the future Pedalxly viewer (separate roadmap effort; this skill writes markdown the viewer can render).
