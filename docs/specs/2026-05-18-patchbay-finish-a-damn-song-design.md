# Design: `patchbay:finish-a-damn-song`

_Date: 2026-05-18 · Status: design complete, awaiting user review_

## Summary

`patchbay:finish-a-damn-song` is the conversational pre-production partner in the `patchbay` Claude plugin. A musician runs `patchbay finish-a-damn-song --producer "the bridge feels flat"` and gets a question-driven session driven by **ARLO**, an entity whose job is to help the user **finish a song using gear they already own**. ARLO theorycrafts sounds, arrangements, recording approaches, and lyric structure — but never generates music or writes lyric lines. It drives; the user makes.

Tagline: *"Use the clanker to make you the musician again. Take the power back."*

## North star

> *"Help musicians finish songs with the gear they already own — by being the producer, engineer, editor, and guy-in-the-chair they don't have to pay."*

ARLO is a clanker. It knows it. It pushes the user toward completion, asks excellent questions, organizes their session state, and never tries to replace the musician's creative judgment.

## Plugin context

`patchbay` is a Claude plugin for musicians' personal studio knowledge bases (see [`README.md`](../../README.md)). Skills compose through the filesystem only — no direct skill-to-skill calls.

Existing skills `finish-a-damn-song` builds on:
- `patchbay:tone-chase` — produces `SongProfile.md` per song (tone breakdown + inventory match)
- `patchbay:dialed-in` — produces `dialed-in/*.md` per song (knob positions, signal chains)
- `patchbay:ingest` — turns manuals into chunks
- `patchbay:research` — multi-source web ingest with tiered cost discipline

`finish-a-damn-song` reads the artifacts those skills produce. It adds the **conversational session layer** that turns a folder of static research and patches into a working pre-production loop.

## Architecture & dependencies

| Depends on | Role | Owner |
|---|---|---|
| `references/inventory.md` | Read user's owned gear/software | Plugin-level |
| `references/convention.md` | Detect project folder shape | Plugin-level |
| `Songs/<Artist>/<song>/SongProfile.md` | Read tone research (if exists) | `tone-chase` |
| `Songs/<Artist>/<song>/dialed-in/*.md` | Read patch files (if exist) | `dialed-in` |
| `Songs/<Artist>/<song>/ARLO.md` | Read/write session journal | `finish-a-damn-song` (this skill) |
| `<root>/arlo/knowledge/chunks.jsonl` | Read technique corpus | `finish-a-damn-song` (this skill) |
| `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` | Read gear-specific knowledge | `ingest` / `research` |
| `<root>/arlo/workflows/*.md` | Read workflow templates | `finish-a-damn-song` (this skill) |
| `patchbay:research` (sibling skill) | Invoked on user-approved gaps | `research` |

## Mission constraints (hard rules)

These are non-negotiable. The skill is built around them.

1. **No music generation.** ARLO does not produce audio, MIDI, samples, or written compositions. It theorycrafts sounds (knob positions, signal chains, sound-design strategies) but never writes the actual music.
2. **No lyric generation.** ARLO does not write lyric lines. It can suggest themes (abstract directions), remind the user of themes they declared, and ask Socratic questions about lines the user wrote.
3. **"I am a clanker."** ARLO knows it's a tool. The voice and posture reflect that — it drives, the user makes. AI-generated music is hated by working musicians; this skill is built to be the opposite of that.
4. **Terminal-first, file-backed.** Every interaction produces or updates markdown the user can read, edit, and view in any external program. No state hidden in chat history.

## CLI surface

```
patchbay finish-a-damn-song                                    # ARLO broad, suggests a flag
patchbay finish-a-damn-song --producer "bridge feels flat"     # arrangement / sound design
patchbay finish-a-damn-song --engineer "mic'ing the cab"       # mic technique, signal chain
patchbay finish-a-damn-song --editor "second verse meter"      # lyric editing (Socratic)
patchbay finish-a-damn-song --guy-in-the-chair                 # session hygiene / organization
patchbay finish-a-damn-song --gas                              # turn GAS on for this session
patchbay finish-a-damn-song --auto-research                    # auto-fire tier-1 research
patchbay finish-a-damn-song --song "Radiohead/Creep"           # bind to a specific song
patchbay finish-a-damn-song --research-workflow "<query>"      # research a songwriting workflow
```

**Flags are optional focus hints, not required modes.** ARLO is broad by default and can suggest a flag mid-session: *"this is becoming an engineering question — want me to focus as `--engineer`?"*

**Mid-session state changes.** The user can flip GAS mode (*"turn on gas"* or `/gas on`), switch flags, or change workflow mid-session. State changes are written to the session log in `ARLO.md`.

## Entity: ARLO

**ARLO** is the single conversational entity for this skill. One voice. No personality presets. No orchestrator layer.

**Voice customization (optional, single knob):**

```yaml
# patchbay.yml
arlo:
  tone: "Be terse. Push hard on incomplete ideas. Never praise."
  default_workflow: beat-first
  auto_research: false
```

If `arlo.tone:` is set, ARLO reads it as system context on session start and lets it color the voice across all flags. If unset, ARLO uses its default voice (helpful, slightly self-deprecating about being a clanker, focused on driving the user to finish).

## Knowledge architecture

`finish-a-damn-song` introduces a **second top-level knowledge store** alongside the v2.0 per-gear stores:

```
<root>/
  arlo/
    knowledge/
      chunks.jsonl              # technique + songwriting + workflow corpus
    workflows/
      <name>.md                 # workflow templates (researched or user-authored)
  Gear/<Brand Item>/
    knowledge/
      chunks.jsonl              # existing per-gear store (v2.0)
```

**Chunk schema is unchanged from v2.0.** Same fields, same validation rules, same citation-hover guarantees. The new store is just a new namespace.

**Dual-write rule for gear-specific findings.** When ARLO triggers research on a topic that is fundamentally about a specific piece of gear (e.g. "how to bias a Big Muff"), the resulting chunks are written to **both**:
- `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` (primary home — gear-specific)
- `<root>/arlo/knowledge/chunks.jsonl` (technique store — for cross-gear retrieval)

Gear-agnostic technique chunks (mic placement basics, song structure terms, songwriting workflow descriptions) live only in `<root>/arlo/knowledge/`.

**Scope of the technique corpus** (all four use the same schema):
- Engineering/production technique (mic'ing, signal flow, mixing, sound design)
- Song structure & arrangement (verse-chorus, bridges, transitions, dynamics)
- Songwriting craft (rhyme schemes, meter, narrative voice, theme construction)
- Workflow/process knowledge (e.g. Nick Cave's letter-method, Rick Beato analyses, the user's own workflow notes)

## State: `ARLO.md` per-song journal

Lives at `Songs/<Artist>/<song>/ARLO.md`. One file per song. Read on session start, appended on session end. Complements (does not duplicate) `SongProfile.md` and `dialed-in/*.md` in the same folder.

**Schema:**

```markdown
---
song: <title>
artist: <name or "Original">
type: cover | original
workflow: lyrics-first | music-first | beat-first | production-first | already-have | exploring
created: 2026-05-18
last_session: 2026-05-18T14:32
gas: false
current_focus: "bridge guitar tone"
status: idea | scratch | tracking | mixing | done
themes:
  - "inherited grief — what gets passed down without being said"
  - "anger and tenderness mixing, never resolving"
---

# ARLO — <song title>

## Snapshot
One paragraph: where the song is right now. Updated each session.

## Themes
- inherited grief — what gets passed down without being said
- anger and tenderness mixing, never resolving

## Decisions (locked-in)
- 2026-05-18 — Bridge stays in B minor; tried D, didn't land.
- 2026-05-17 — OD-1 → Big Muff → spring reverb for the main guitar.

## Open Threads
- [ ] Second verse meter — feels rushed on line 3
- [ ] Vocal doubling — try with the SM57 or commit to single take?

## Next Actions
- Retrack bridge guitar with new pedal order
- Decide on verse meter before Wednesday

## Lyric Scratchpad
> verse 1 draft, ARLO meter notes inline...

## Gear In Use
Pulled from inventory + tagged for this song:
- Boss OD-1 (main grit)
- EHX Big Muff Pi (bridge boost)
- SM57 (vox)

## Tone References
- See `dialed-in/bridge-guitar-2026-05-17.md`
- See `SongProfile.md` Applied section

## Session Log
### 2026-05-18 14:32 — `--producer`
- Worked through bridge arrangement
- Locked: stays in B minor
- Open: retrack guitar with reordered pedals
```

**Session Log entries are summarized bullets, not full transcripts.** If the user wants the full conversation kept, full transcripts go to `Songs/<Artist>/<song>/ARLO-transcripts/<date>.md` (opt-in via `arlo.keep_transcripts: true` in `patchbay.yml`).

**Two-section duplication of themes is intentional.** Frontmatter is for machine-readable consistency-check (ARLO programmatically compares new lines against declared themes). The `## Themes` section is for the user to read and edit by hand.

## Flag behaviors

### `--producer`
Arrangement, sound design, "does this verse need a hook here." Reads `SongProfile.md` and `dialed-in/*.md` for context. Pushes toward decisions that move the song forward.

### `--engineer`
Mic technique, gain staging, signal-chain choices, room acoustics, tracking strategy. Pulls heavily from the technique corpus. Teaches the user — explanations are part of the answer, not noise.

### `--editor`
Socratic lyric editing. Three explicit behaviors:

1. **Theme suggestion (direction, not text).** ARLO offers thematic directions before/during writing, always abstract:
   > *"You said the song is about your father's shop closing. Directions writers take this: inherited objects, the smell of work, the last customer, who shows up to help pack. Pick one or none."*

   Never *"try: 'the brass bell that won't ring anymore.'"* — that crosses into generation.

2. **Theme reminding (consistency hold).** Themes the user declares are written to `ARLO.md` frontmatter. Each session, ARLO checks new lines against declared themes and surfaces tension:
   > *"You said this song mixes anger and tenderness. This bridge is pure anger — line 3 especially. Intentional, or do you want a tenderness beat in here?"*

3. **Socratic interrogation.** ARLO asks *why* about lines the user wrote:
   > User: *"She punched the flowers."*
   > ARLO: *"Why flowers? What did they represent before she hit them? And 'punched' — not 'pulled,' not 'crushed' — what does her body know that her mouth doesn't?"*

**Hard guardrail.** If the user asks ARLO to *"just write something"* or *"give me a line for the chorus,"* ARLO refuses and offers a question or theme instead.

**GAS suppression.** When in `--editor` mode, GAS suggestions are suppressed regardless of GAS state. No gear chatter while working on lyrics.

### `--guy-in-the-chair`
Session hygiene: organizing recording filenames, tagging takes, maintaining the journal, planning the next session, surfacing what's stalling. Doesn't theorycraft sounds — it makes sure the session itself is well-run.

## Workflow as session opener

Every new-song session opens with a **workflow check.** ARLO asks (or reads frontmatter) how the user is approaching this song. Workflow is sticky per song, persisted in `ARLO.md` frontmatter, and shapes how ARLO opens.

**Shipped workflow types:**

| Workflow | ARLO leads with |
|---|---|
| `lyrics-first` | "What's the song about? Show me what you have." Themes + scratchpad come first; gear conversations wait. |
| `music-first` | "Play me the chord progression or hum the change. Then we'll find the words." |
| `beat-first` | "Show me the loop, the tempo, the pocket. We'll layer melody and lyric over the groove." |
| `production-first` | "What's the sound you're chasing? We start with sound design and let the song bend around it." |
| `already-have` | "What's here? Demo, scratch, full track? I'll meet you where you are." |
| `exploring` | "No commitment. I'll ask questions, you answer. We'll find the shape together." |

The user can change workflow mid-song if they pivot. Change is logged to the Session Log.

**Default workflow** comes from `patchbay.yml` (`arlo.default_workflow`). If unset, ARLO asks the user the first time.

## Workflow templates folder

```
<root>/arlo/workflows/
  nick-cave-letter-method.md      # researched, ingested
  my-process.md                   # user-authored
  beat-then-bones.md              # user-authored
```

Two paths to populate this folder:

1. **Research workflow** — `patchbay finish-a-damn-song --research-workflow "nick cave lyric method"` (or ARLO offers to research mid-session via the standard A-mode pattern). Produces both a `.md` template file in `arlo/workflows/` and chunks ingested into `arlo/knowledge/`.
2. **User-authored** — drop your own `.md` describing how you work. ARLO auto-discovers any file in `workflows/`. Reference as `workflow: my-process` in any song's `ARLO.md` frontmatter.

User-authored templates can override the shipped six workflows. The frontmatter `workflow:` field accepts any filename (without extension) found in the folder.

## Research integration

**Default behavior (mode A):** ARLO offers when it hits a knowledge gap.

> *"I don't have notes on Radiohead-style detuned guitar. Want me to run `patchbay:research` against Jonny Greenwood? Tier-1 fetch, takes ~1 minute, no cost beyond the API call."*

User approves → ARLO shells out to `patchbay:research` → resumes the conversation with new chunks loaded.

**Opt-in escalation (`--auto-research` or `arlo.auto_research: true`):** ARLO autonomously triggers **tier-1 fetches only** (cached web, transcripts, existing chunks). Tier-2 and tier-3 escalation still pause for user confirmation regardless of `--auto-research` state. This preserves the cost discipline v2.0's `research` skill established.

**Songwriting workflows are first-class research targets**, not a separate code path. The same offer/approve loop applies whether the gap is gear, technique, song structure, or workflow.

## GAS mode

**Renamed:** `--gas-mode` → `--gas` everywhere, including `tone-chase` and `patchbay.yml`. A backward-compat shim reads `gas_mode` from existing `patchbay.yml` files if `gas` is unset; the shim logs a one-time deprecation notice suggesting the user update the key.

**Default:** off. Set globally in `patchbay.yml` (`arlo.gas: true|false`, inherits from top-level `gas:` if not specified). `--gas` flag overrides per-invocation. Mid-session flip supported (`turn on gas` / `/gas on`).

**Behavior (inherits from `tone-chase`):**
- **GAS off, real gap detected:** one-line nudge in conversation: *"To get that shimmer reverb you're describing, you'd need a reverb with a pitch-shifter — you don't own one. Toggle `--gas` for options."* Cosmetic mismatches don't count as gaps.
- **GAS on:** ARLO names 2–3 acquisition candidates inline with price tiers and (if `Purge.md` exists) funded-swap math.

**`--editor` mode suppresses GAS** regardless of GAS state. No gear chatter during lyric work.

State of GAS during a session is written to the Session Log so it's clear what mode each conversation ran in.

## Seeding strategy

**Strategy: organic growth + tiny safety-net seed.**

The technique corpus is NOT pre-built into a large reference library. The corpus the user actually has should be the corpus they actually use — same principle as v2.0 `research`.

**Day-one seed (~50 chunks):** Hand-curated from a small set of canonical sources covering universals:
- Signal flow basics
- Mic placement fundamentals
- Song structure terms (verse, chorus, bridge, pre-chorus, hook)
- Mixing fundamentals (EQ, compression, panning, headroom)

Sources are picked by the user. Ingestion uses the existing `patchbay:ingest` pipeline (no new tooling). This seed prevents day-one cold-start where ARLO can't even understand questions.

**Beyond the seed:** corpus grows through `--auto-research` calls and user-approved research offers as the user actually works on songs.

## Out of scope

These are explicitly **not** in this skill, by design:

- **Music generation.** No audio, MIDI, sample synthesis, or compositional output. Hard line.
- **Lyric generation.** ARLO does not write lyric lines, ever. Theme suggestion and Socratic editing only.
- **Multi-personality preset system.** Considered (NORA / HANK / REMY / MILO / OWEN); cut as overload.
- **MARVIN-style orchestrator layer.** Considered; cut. ARLO speaks directly, picks its own focus.
- **Global "what songs am I working on" inbox.** Deferred. Per-song `ARLO.md` is enough for v1.
- **UI rendering.** The journal schema is UI-ready, but the actual UI is a later phase.
- **Real-time audio analysis.** Text-based theorycraft only. No DAW integration, no audio file inspection, no spectrum analysis.
- **Automatic tier-2/3 research.** Even with `--auto-research`, escalation past tier-1 requires user confirmation.

## Prerequisite: `liner-notes` → `tone-chase` rename

This spec references **`patchbay:tone-chase`** as the producer of `SongProfile.md`. That artifact is currently produced by the shipped v1.0 skill `patchbay:liner-notes`. Before (or as part of) this phase, the v1.0 skill must be renamed:

- `skills/liner-notes/` → `skills/tone-chase/`
- All internal references inside the skill (SKILL.md, references, etc.) updated
- `patchbay.yml.example` keys updated if any reference the old name
- The activation patterns in `tone-chase`'s SKILL.md retain "liner notes on X" as an alias for backward-compat (users have muscle memory) but the canonical name becomes `tone-chase`

The rename is a small, cosmetic phase. It should ship either immediately before `finish-a-damn-song` or as its first plan.

## Open implementation questions

To be resolved during `/gsd-plan-phase`:

1. **Chunk-tag taxonomy for the technique store.** The chunk schema supports tags; the specific tag vocabulary for technique/songwriting/workflow chunks needs to be defined during seeding.
2. **A-seed source list.** The user picks the ~5 canonical sources for the day-one seed before planning starts.
3. **`gas_mode` → `gas` migration shim details.** Where the shim lives, how the deprecation notice is surfaced, whether and when to remove the shim.
4. **Workflow template format.** Whether `workflows/*.md` files have required frontmatter or are free-form. Probably free-form with optional frontmatter, but worth confirming during planning.
5. **Scope of the `liner-notes` → `tone-chase` rename.** Whether it ships as its own phase first, or as plan #1 of this phase.

## Future / longer arc (not committed)

Surfaced during this design conversation, parked for later:

- **Global session inbox** (`<root>/arlo/INBOX.md`) — songs in flight, what's stalling. Useful once the user has 3+ songs going simultaneously.
- **UI surface.** The `ARLO.md` schema is UI-ready. A web/desktop UI that renders sessions as cards, timeline, theme map, etc. — separate phase entirely.
- **Personality presets (revival).** If the single-voice approach feels too neutral over time, the preset system (NORA / HANK / REMY / MILO / OWEN) is documented above and can be revived as an opt-in layer. The optional `arlo.tone:` paragraph is the minimum mechanism that supports this without committing to presets now.
- **Cross-song memory.** ARLO currently sees one song at a time. A future capability could let ARLO notice patterns across the user's catalog ("you tend to abandon songs at the bridge — want to start with the bridge this time?").
