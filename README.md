# patchbay

A Claude Code plugin for musicians.

Patchbay is a project-agnostic toolkit that helps musicians use what they
already own. Point it at a folder — gear notes, manuals, research, plugin
inventory — and it adds the skills to inventory, research, design patches,
and chase the tones behind the songs you love.

GAS mode (Gear Acquisition Syndrome) is off by default. The skill is built
to lean on substitution from your existing rig. When you do want to add or
swap, GAS mode surfaces honest acquisition options — including funded swaps
from a sell list you maintain yourself.

## Shipped Skills

- **`patchbay:liner-notes`** — research the rig and tone behind a song or
  artist. Produces a `SongProfile.md` with sourced gear breakdown and an
  inventory-matched Applied section. *(v1.0)*
- **`patchbay:dialed-in`** — design or recall a patch. Saves dial-in
  sessions as structured markdown (knob positions, toggle states, signal
  chain, technique notes) anchored to a specific song + gear substitution.
  *(v1.0)*
- **`patchbay:ingest`** — turn a gear manual PDF into a populated,
  schema-valid `chunks.jsonl` for that gear. Every image described, every
  page provenance-tracked, citation-hover ready. *(v2.0)*
- **`patchbay:research`** — multi-source web ingest (Equipboard, Reddit,
  articles, YouTube) into the same per-gear knowledge store. Cheap-by-default
  + user-driven escalation through a tier-1 / 2 / 3 / 0 fetch ladder. No
  auto-fallback — failures go to `failures.log`, you decide what to escalate.
  *(v2.0)*
  - `--review-failures` — interactive escalation loop
  - `--citations <gear>` — surface URLs referenced by N distinct sources
  - `--verify <gear> <url>` — mark a recommendation verified → ingest +
    promote to high-trust

## Status

**Shipped:**
- ✅ **v1.0 dialed-in** — `liner-notes` + `dialed-in` skills (2026-05-07)
- ✅ **v2.0 gear-knowledge** — chunk schema + per-gear knowledge store +
  `ingest` + `research` + citation tracking (2026-05-18)

138 pytest cases green, 24/24 v2.0 requirements satisfied. See
[`.planning/MILESTONES.md`](.planning/MILESTONES.md) for the full delivery
log and [`.planning/RETROSPECTIVE.md`](.planning/RETROSPECTIVE.md) for what
worked / what didn't.

## Roadmap

The big arc: build the substrate (done), then build the consumers that turn
the substrate into a usable surface for musicians. Specifics for the next
milestone get scoped via `/gsd-new-milestone`.

### 📋 v3.0 — Ordered candidates (top = next, bottom = last)

1. **`patchbay:tone-chase`** — conversational pre-production partner
   driven by **ARLO**, an entity whose job is to help you *finish a song
   using gear you already own*. Four optional focus flags (`--producer`,
   `--engineer`, `--editor`, `--guy-in-the-chair`), per-song `ARLO.md`
   journal, workflow-as-session-opener, Socratic-only lyric editing
   (theme suggestion, theme reminding, asks-you-why — never writes lyrics
   for you), `--gas` rename from `--gas-mode`. Design committed:
   [`docs/specs/2026-05-18-patchbay-tone-chase-design.md`](docs/specs/2026-05-18-patchbay-tone-chase-design.md).
2. **`patchbay:midi`** — generate `.mid` / `.syx` files or send real-time
   MIDI via a small helper. Moved up from the longer arc because it's
   interesting and creative.
3. **`patchbay:soundcheck`** — first-time setup; detect or scaffold folder
   convention. Makes everything portable across users with different
   gear-folder layouts.
4. **`patchbay:add-gear`** — onboard a piece of gear with a structured
   profile; the natural front door once `ingest` exists.
5. **Conversational AI hover-citation UX** — the consumer of the
   gear-knowledge substrate. Ask a question, get answers where every
   sentence deep-links to source. May fold into `tone-chase`'s eventual
   UI surface.
6. **CITATION-02 primary-source independence** — lift the v2.0 known
   limitation where same-class re-publication under-counts.
7. **Multi-gear tone-graph queries** — cross-gear recommendations that
   walk the `artist_usage` + `cross_ref` edges Phase 3 produces
   (e.g. "what else do artists who use my Boss BF-3 also use?").
8. **Skill rename:** `liner-notes` → `rip-off`. Cosmetic, light-touch phase
   to make the plugin name itself a wink.
9. **`patchbay:purge`** — review inventory for sell candidates. Last on the
   list.

### 🧭 Longer arc (not committed)

- **Whisper transcription for YouTube** — auto-captions are sufficient
  today (validated spike 002a/002c). A quality upgrade only if the
  hover-citation UX needs frame-accurate transcripts.
- **Bounding-box provenance** — `{source, location_anchor}` is sufficient
  for now; bbox-level deep links are a future precision upgrade.

### Out of scope

- **User taste profile** — independent of the substrate; intentionally
  deferred. Seed at [`seeds/user-taste-profile.md`](.planning/seeds/user-taste-profile.md).
- **Tier-2 extension auto-install** — production detects an empty
  `list_connected_browsers` and surfaces an install hint; no auto-install.

See [`.planning/ROADMAP.md`](.planning/ROADMAP.md) for the live roadmap and
[`docs/specs/`](docs/specs/) for the original design specs.

## Project-agnostic by design

Patchbay reads whatever folder structure you have. It works best with a
[Pedalxly](https://github.com/colfitt/Pedalxly)-style layout
(`Gear/<Brand Item>/`, `Software/<Brand Product>/`, `Songs/<Artist>/<song>/`),
but adapts to flat folders or a custom convention via a per-project
`patchbay.yml`.

Pedalxly is the canonical test case.

After v2.0, every gear-related skill writes into a unified per-gear
knowledge store at `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` —
append-only JSONL, schema-validated, citation-ready.

## License

[TBD]
