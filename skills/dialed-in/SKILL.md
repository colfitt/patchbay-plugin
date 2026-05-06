---
name: dialed-in
description: Generate and save gear dial-in sessions as structured markdown — knob positions, toggle states, signal chain context, and technique notes anchored to a specific song and gear substitution. Activates on "dial in [song]", "dial in my [gear] for [song]", "dial in my [gear] for the [role] in [song]", "/dial-in [query]", and as a follow-up after liner-notes.
---

# patchbay:dialed-in

Save and generate gear dial-in sessions as structured, searchable files. When you've approximated a target tone using owned gear, `dialed-in` produces a markdown file with knob positions, toggle states, signal chain context, and technique notes — anchored to a specific song and gear substitution.

**Before starting any dial-in**, read these three reference files from the plugin root:
- `references/convention.md` — project paths, folder layout, slug rules
- `references/inventory.md` — how to read and normalize the user's owned gear
- `references/sources.md` — per-site fetch strategies

## Invocation patterns

Activate on any of these patterns:

```
"Dial in [song] by [artist]"                         → show substitution menu
"Dial in my [gear] for [song]"                       → direct, offer rest after
"Dial in my [gear] for the [role] in [song]"         → direct + specific role
"/dial-in [query]"                                   → same routing
```

**Follow-up from `liner-notes`:** if invoked in the same session as a `liner-notes` run, song context (artist, song, Applied section) is already loaded — skip the SongProfile lookup and use in-session context.

## Process

### Step 1: Resolve target

Identify artist and song title. Load `SongProfile.md` from `<songs_root>/<Artist>/<song-slug>/` (resolve `songs_root` from `patchbay.yml` `songs_root` key, or default to `Songs/` per `references/convention.md`).

If no SongProfile exists, stop:

> "No liner notes found for [Song] by [Artist]. Run `liner-notes` first, then come back."

If invoked as a follow-up to `liner-notes`, use in-session context — skip the file read.

### Step 2: Load substitutions

Read the `## Applied` section of SongProfile.md. Build a substitution list:

```
1. JHS Kilt v10  →  Marshall ShredMaster       (Distortion / chorus chunk)
2. Neural DSP Iridium  →  Fender Eighty-Five   (Clean amp)
3. Boss CE-2W  →  EHX PolyChorus               (Chorus layer)
```

If Applied is empty or has no substitutions, stop:

> "No gear substitutions found in Applied. Check that your GearProfile slugs are correct or re-run `liner-notes`."

### Step 3: Select gear to dial in

**If the user specified gear:** go directly to Step 4 for that substitution.

**If no gear specified:** present the substitution menu:

> "Here are the substitutions for [Song]. Which would you like to dial in?
> 1. JHS Kilt v10 → Marshall ShredMaster (Distortion)
> 2. Neural DSP Iridium → Fender Eighty-Five (Clean amp)
> 3. Boss CE-2W → EHX PolyChorus (Chorus)
> Enter a number, multiple numbers (1,3), or 'all'."

### Step 4: Check for existing dial-in files

For each selected substitution, check whether `<song-folder>/dial-in/<owned-slug>--<target-slug>.md` exists.

If it does, present the re-run menu:

> "A dial-in exists for [Owned Gear] → [Target Gear] on [Song]. What would you like to do?
> 1. **Refresh** — re-research and rewrite
> 2. **Extend** — add notes, keep existing settings
> 3. **Leave it** — skip this one
> 4. **Start over** — wipe and rewrite"

### Step 5: Research target gear

1. Read `GearProfile.md` for the owned gear — extract controls, toggles, topology. If GearProfile.md doesn't include a control map (current GearProfiles typically don't), fall back to `WebSearch "[owned gear] controls knobs manual"` to establish the control topology before mapping.
2. Check `dial-in/sources/<target-gear-slug>-<date>.md` — if a recent cache exists (within 30 days), use it. Otherwise:
   - `WebSearch "[target gear] knob settings characteristics tone"`
   - `WebSearch "[target gear] [artist] [song] settings"` if artist-specific info exists
   - Save result to `dial-in/sources/<target-gear-slug>-<YYYY-MM-DD>.md`
3. Pull relevant characteristics from SongProfile `## Research` (confidence levels, signal chain notes).

### Step 6: Generate dial-in

For each owned-gear control, map to the target gear's character. Structure:

**Toggles / switches first** — these define the topology and should be set before knobs.

**Knobs** — one entry per control with:
- Clock position (e.g., `2:00`, `9:00`)
- Mapping rationale: what it corresponds to on the target gear and why

**Signal chain context** — if the role involves an amp or interface, include settings for the owned amp/interface (e.g., Iridium) alongside the pedal settings.

**Technique notes** — if sources mention playing technique that materially affects the tone, include it. Settings without technique context can mislead.

**Fine-tuning guidance** — 2–3 "if it sounds X, try Y" lines for dialing in by ear.

### Step 7: Write dial-in file

Create `<song-folder>/dial-in/` if it doesn't exist.

Write `dial-in/<owned-gear-slug>--<target-gear-slug>.md` with full frontmatter (see Data model).

### Step 8: Offer remaining substitutions

After writing, list any undialed substitutions from the session:

> "Dialed in. Want to continue with the remaining substitutions?
> 2. Neural DSP Iridium → Fender Eighty-Five
> 3. Boss CE-2W → EHX PolyChorus
> Enter a number, multiple, 'all', or 'done'."

If all substitutions are done, suggest a commit:

```
feat: add dial-in for Creep by Radiohead (JHS Kilt v10)
```

## Data model

### File location

```
<songs_root>/<Artist>/<song-slug>/
  SongProfile.md
  sources/
  dial-in/
    <owned-gear-slug>--<target-gear-slug>.md
    sources/
      <target-gear-slug>-<YYYY-MM-DD>.md
```

### Filename convention

`<owned-gear-slug>--<target-gear-slug>.md`

Double-dash separates owned from target. Slugs follow the same convention as GearProfile folders: lowercase, spaces → hyphens.

Examples:
- `jhs-kilt-v10--marshall-shredmaster.md`
- `neural-dsp-iridium--fender-eighty-five.md`

### Frontmatter schema

```yaml
---
type: dial-in
song: Creep
artist: Radiohead
song_slug: creep
artist_slug: radiohead
date: 2026-05-06
owned_gear: JHS Kilt v10
owned_gear_slug: jhs-kilt-v10
target_gear: Marshall ShredMaster
target_gear_slug: marshall-shredmaster
role: Distortion / chorus chunk
confidence: med        # inherited from SongProfile Research confidence
sources:
  - sources/marshall-shredmaster-2026-05-06.md
tags: [radiohead, creep, jhs-kilt-v10, marshall-shredmaster, distortion]
---
```

### Body structure

```markdown
# [Owned Gear] → [Target Gear]
## [Song] by [Artist] — [Role]

## Toggles / Switches
| Control | Position | Why |
|---------|----------|-----|

## Knobs
**[Knob name]**
Position: [clock value]
[Mapping rationale]

---

## Signal Chain
[Amp/interface settings if applicable]

## Technique
[Playing technique notes if materially relevant]

## Fine-tuning
- If too [X]: [adjustment]
- If too [Y]: [adjustment]

## Sources
- [source-file](sources/source-file.md)
```

## Error handling

| Situation | Behavior |
|---|---|
| No SongProfile.md | Stop. Direct user to run `liner-notes` first |
| Applied empty / no substitutions | Stop. Suggest re-running `liner-notes` with gear inventory present |
| Owned gear not in inventory | Proceed with generic category guidance; note "not found in inventory" |
| Target gear controls unknown after research | Generate character-based guide instead of knob positions; flag as low confidence |
| Dial-in file already exists | Re-run menu: Refresh / Extend / Leave it / Start over |
| No research sources found | Generate from SongProfile only; mark confidence low; recommend verify by ear |
| Multi-player song | Use `role` field to disambiguate (e.g., "Jonny Greenwood / chorus chunk") |
| Amp not in inventory | Still include amp-side notes for owned amp; describe original amp's character |

## UI layer notes

These decisions were made with a future interface in mind:

| Decision | UI implication |
|---|---|
| One file per gear pair | Gear profile page: "All tones dialed in on this pedal" — each file is a card |
| `tags` in frontmatter | Full-text search by song, artist, or gear — no separate index needed |
| `owned_gear_slug` + `target_gear_slug` | Filter: "show all dial-ins using my Kilt" across entire library |
| `role` field | Group dial-ins by function (distortion, chorus, tremolo) not just gear name |
| `dial-in/sources/` cache | UI can surface sourcing confidence: "based on 2 sources" |
| Clock-position format (`2:00`, `9:00`) | Parseable for visual pedal control diagram — knob rendered at clock angle |
| Toggle states (UP/DOWN) | Binary UI toggle, directly mappable to a pedal schematic component |
| Re-run menu | Maps 1:1 to a UI modal with four actions |
| "Offer remaining subs" step | Maps to a checklist UI: tick which substitutions to continue with |
| `confidence` field | UI can de-emphasize or flag low-confidence dial-ins visually |
| Empty-state errors (no SongProfile, no Applied) | Two recoverable empty states — both have a clear next action for the UI to surface |

**Clock positions are the most load-bearing UI decision.** The `2:00` / `9:00` format is human-readable in markdown today and directly renderable as a knob angle in a future interface without any format migration.
