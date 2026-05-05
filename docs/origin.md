# Patchbay Plugin

Working notes for a Claude plugin (`patchbay`) made of multiple skills that help musicians work with their gear, manuals, research, and patches. Pedalxly is the seed project / first test case.

_Status: brainstorming, paused before scope-narrowing. Resume at "Where we left off"._
_Last update: 2026-05-05._

## Purpose

A Claude-side toolkit that lets a musician operate their personal studio knowledge base — adding gear, ingesting manuals and research, designing patches, and (eventually) talking to gear over MIDI.

## Core constraint: project-agnostic

The Pedalxly repo's conventions (`Gear/<Item>/`, `Software/<Brand Product>/`, `research/{books,transcripts,links}/`) inform the design but **must not be required**. The skill should:

- **Detect** existing structure and respect it.
- **Bootstrap** a sensible default if the user points at a fresh folder.
- Be **configurable** via something like a `patchbay.yml` at the project root that captures naming, paths, and conventions.

The Pedalxly repo is the first-and-best test case, but the same skill should work for someone who just has a `~/Music/Studio/Manuals/` folder full of PDFs.

## Capability space

Brainstorm output. Not all of this is v1.

### Inventory & cataloging
- **Add gear** — onboard a pedal/synth/instrument with a structured profile (frontmatter: brand, model, category, MIDI, power, IO, tags).
- **Add software/plugin** — same shape, software variant.
- **State tracking** — own / sold / wishlist / loaned / in-for-repair / broken.
- **Service log** — recaps, jack replacements, firmware versions, mods.
- **Wishlist + redundancy check** — "do I already own something that does this?"
- **Insurance / serial export** — clean inventory PDF.

### Manual handling
- **Ingest** — drop in a PDF, OCR-fallback if scanned, optional chapter split.
- **Quick lookup** — "how do I tap-tempo on the Volante?" answered from the manual.
- **Cross-reference** — single MIDI-CC cheat sheet built from every manual you own.

### Research
- **YouTube ingest** — transcript → markdown with frontmatter, filed under the right gear's `research/transcripts/`.
- **Article / Reddit / blog ingest** — readability + html2md → `research/links/`.
- **Book / chapter ingest** — `pdftotext` + Tesseract fallback.
- **Deep research a piece of gear** — signature uses, common patches, alternatives, comparisons; cites local files.
- **Technique research across gear** — "parallel compression" referencing your specific tools.
- **"Teach me X" curriculum** — lesson plan built from your owned manuals + research.

### Patching
- **Build a patch** — "warm shimmer on the Volante" → parameter values + signal-flow notes.
- **Recall** — "what was that warm synth I built last month?"
- **Compare two patches** — diff parameters, explain what each is doing.
- **Substitution** — "if I sold X, could Y cover this patch?" using inventory.
- **Genre starter packs** — "ambient signal chain from what's in this folder."

### Song / artist tone research
Sourced from sites like Equipboard, Premier Guitar rig rundowns, Sound on Sound, interviews, and gear-thread Reddits.

- **"Get the sound of \<song\>"** — research the gear and signal chain used on a recording.
- **Folder layout** — write to a top-level `Songs/<Artist>/<song-slug>/research.md` with sources cited.
- **Cross-reference with inventory** — "of the gear they used, here's what you own and here's what's missing."
- **Patch translation** — generate a usable patch using only the user's inventory (substitution-aware).
- **Artist-level research** — same flow, scoped to an artist's whole rig over time.

### GAS mode (cross-skill flag)
**G**ear **A**cquisition **S**yndrome — an opt-in mode that adds purchasing suggestions to any research output.

- Applies to `song-research` ("the original used a Whammy II — here's the modern equivalent at $X, plus a $Y alternative")
- Applies to `patch` ("you can get 80% of this sound; a JHS Pulp 'N Peel would close the gap")
- Applies to `research` ("if you bought one Eventide, the H9 covers the most ground")
- Off by default. User must explicitly enable per-call or via `patchbay.yml`.

### MIDI integration
See "MIDI feasibility" below for what's realistic.

- **Generate `.mid` files** — note + CC automation; user drags into Ableton/Logic.
- **Generate SysEx patch dumps** (`.syx`) — many modern pedals/synths accept these.
- **Real-time MIDI to gear** — via a small Rust/Node helper (`midir` / `@julusian/midi`) that the skill shells out to. Gives you "set tap tempo on the Volante to 120" → it actually happens, no DAW required.

### Cross-piece intelligence
- **MIDI CC reference** — combined cheat sheet, pulled from manuals.
- **Power / pedalboard layout** — mA budget, signal-path planning.
- **Compatibility check** — does pedal X handle stereo from pedal Y?

### Sessions & live
- **Setlist signal chain** — plan rig per song.
- **Session notes** — what worked, what to try next.
- **Pre-gig checklist** — derived from your gear list.

### Project bootstrap
- **First-time setup** — point at a folder, skill scaffolds structure (or detects existing convention).
- **Adapt to existing layout** — respect any folder shape the user already has.

## MIDI feasibility

| Capability | Effort | How |
| --- | --- | --- |
| Generate `.mid` clips | Low | Pure file write; user drags into DAW. |
| Generate `.syx` patch dumps | Low–Med | File write; SysEx spec from each device's manual (which we already have). |
| CC reference tables | Low | Extract from manuals during ingest. |
| Real-time MIDI send | Med | Small Rust CLI (`midir`) or Node helper (`@julusian/midi`). Skill shells out: `pdx-midi send --device "Volante" --cc 14 --value 80`. |
| Real-time MIDI receive | Med | Same helper, listens; useful for capturing patch state from gear. |

Claude can't open CoreMIDI ports directly, so anything real-time needs the sidecar helper.

## Architecture decision: plugin, not single skill

The capability list spans too many independent surfaces (inventory, research, patching, MIDI, sessions). One mega-skill would be unfocused and hard to evolve.

The right shape is a **plugin** containing multiple **single-purpose skills**, each scoped tightly. Names favor legitimate music-industry terminology where it reads cleanly to a working pro; otherwise stay plain.

Plugin: **`patchbay`**. The metaphor — a patchbay is the central hub of every studio, the thing every piece of gear plugs into and that knows every connection. The plugin is the digital version: it knows the user's gear and how the pieces relate.

Skills:
- `patchbay:soundcheck` — first-time scaffold or convention-detection
- `patchbay:add-gear` — onboard a gear item
- `patchbay:purge` — review inventory for sell candidates; make room
- `patchbay:ingest` — pull in a manual, article, video, or book chapter
- `patchbay:research` — deep-research a piece of gear or a technique
- `patchbay:liner-notes` — research the rig/tone behind a song or artist; writes to `Songs/<Artist>/<song-slug>/`
- `patchbay:dial-in` — design or recall a patch
- `patchbay:midi` — generate `.mid` / `.syx` or send real-time MIDI via helper

Plus a **GAS mode flag** that several skills consult — adds acquisition *and replacement* suggestions to research and patch outputs. Off by default.

GAS mode integration:
- `liner-notes` **Gear Acquisition** section, when GAS mode is on, reads both the wishlist and `Purge.md` to suggest **funded swaps** ("sell X to afford Y").
- When GAS is off but the song needs gear the user doesn't own, the section renders a single-line nudge — honest, never pushy. Users dislike GAS but acknowledge it's sometimes necessary to chase a sound.
- `dial-in` and `research` GAS output works the same way.
- The "GAS as discipline" framing — make room before adding — comes from this integration.

Plugin-wide concerns (config file, folder convention, shared "what gear do I own" lookup, GAS flag, sell-candidate list) live in the plugin, not in any single skill.

Plugin name decided: **`patchbay`**. Skill names favor real music-industry terms where they read cleanly to a working pro (`soundcheck`, `liner-notes`, `dial-in`); otherwise plain (`add-gear`, `purge`, `ingest`, `research`, `midi`).

## Open questions for when we resume

1. **Plugin name.** Has to read well to non-Pedalxly users.
2. **Config file location & shape.** `patchbay.yml` at project root? Embedded in an existing config? Per-folder override?
3. **Convention detection.** What signals tell the skill "this is a Pedalxly-shaped repo" vs "this is a flat folder of PDFs"? Probably the existence of `Gear/`, `Software/`, etc.
4. **MIDI helper boundary.** Where does it live — separate repo, sibling to the Pedalxly Rust CLIs in `rust-tools/`, or distributed with the plugin?
5. **First skill to spec in depth.** D1 path picked; candidates: `add-gear` (smallest, unblocks others), `patch` (highest "wow" without web fetches), `song-research` (most distinctive — answers "I want the sound of Creep").
6. **State sharing between skills.** Does `patch` need to read inventory written by `add-gear`? If yes, the plugin needs a shared read API.
7. **Relationship to existing Pedalxly Rust CLIs.** `add-youtube`, `add-link` (and the upcoming `add-book`) already exist as Rust binaries. Does `patchbay:ingest` shell out to them, or do they get absorbed?

## In-progress design: `song-research`

**North star** — quoted from user: *"Help, or prevent GAS, by using what they already own."* Default mode optimizes for substitution (use what you own). GAS mode flips it to acquisition.

**Output shape: E3 layered.** Single markdown file per song with three sections:
1. **Research** — gear used, signal chain, sources cited.
2. **Applied** — substitution-aware patches and signal chains using the user's inventory.
3. **Gear Acquisition** — full acquisition + funded-swap suggestions when GAS mode is on. When GAS is off but the user's inventory has a real gap relative to the song's gear, the section still renders a one-line nudge ("GAS mode is off; you'd need a tape-echo pedal and a fuzz to fully match — toggle GAS on for specifics"). Honest about the constraint, never pushy.

Designed so a future viewer can render it as a navigable personal-wiki page.

**Folder layout (F1):** Songs and artists are first-class wiki citizens.
```
Songs/<Artist>/<song-slug>/
  SongProfile.md     # frontmatter + 3 sections + Corrections
  sources/           # raw scraped content with date stamps
  patches/           # generated patch files, optional
Artists/<Artist>/
  ArtistProfile.md   # rig-over-time, signature sounds
  sources/
```

**User corrections (G1):** Lightweight `## Corrections` section in `SongProfile.md`, populated conversationally ("Claude, that's wrong — it was the Whammy IV"). The skill writes `## Research`; corrections append to `## Corrections` with date + rationale; `## Applied` reads both, with corrections winning. Re-running research never overwrites corrections.

**Patch boundary — song as creative launchpad.** `song-research` writes `## Applied` as **prose** (signal chain, character notes, "what each piece is doing"), plus a `## Where next` list of explicit follow-up prompts:
- *"Dial me settings for the Whammy and Vox using what I own."* → patches saved to `patches/<part>.md`.
- *"Cover-friendly version using only my pedalboard."* → patches saved.
- *"Swap the Vox for my Iridium and slow this to half-speed."* → variant notes saved, optionally spawns a new sibling song folder.

Patches and variants are produced **conversationally**, on request — not auto-generated from research. `patchbay:patch` remains the deep tool for standalone patch creation, comparison, and recall. The two skills compose through the filesystem (patches written by either land in the same place).

**Inventory cross-reference (I2):** A plugin-level helper walks `Gear/` and `Software/` folders, parses frontmatter, exposes a normalized list. The `setup` skill writes a `patchbay.yml` for users without Pedalxly's layout. **Generic-substitution fallback** when inventory's missing or partial — `## Applied` always renders, with category-level recommendations ("use any tape echo: Volante, El Capistan, Memory Man, MXR M292"). Becomes more specific as the user adds gear.

**Data sources (H2):** Targeted scrapers for high-signal sources, web-search fallback for the rest.
- **Equipboard** — parse their structured rig page if reachable. Real risk: Cloudflare may block direct fetch; falls back to web search for that site if so.
- **YouTube** rig rundowns — reuse the existing `add-youtube` Rust CLI to pull transcripts.
- **Premier Guitar / Sound on Sound / Tape Op** — `WebFetch` + readability + html2md (similar to `add-link`).
- **Everything else** — `WebSearch` finds articles; `WebFetch` reads them.
- **Citations** — every claim in `## Research` references a file under `sources/<site>-<date>.md`.

## Where we left off

Brainstorming flow paused at the **scope-decision step**. We had narrowed to:

- **D1: Decompose first, design one skill.** Sketch the plugin shape (decided above — plugin with ~6 skills), then pick *one* skill to spec in detail. Future skills get their own brainstorms later.

User selected D1.

**Next step on resume:** sketch the plugin shape one level deeper (file layout, shared config, how skills compose), then pick the first skill to spec — `add-gear` and `patch` are both candidates. After that, return to the brainstorming flow at "ask clarifying questions" for the chosen skill, then "propose 2–3 approaches," then write a design spec under `docs/superpowers/specs/`.
