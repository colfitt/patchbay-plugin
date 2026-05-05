---
name: liner-notes
description: Research the gear and tone behind a song or artist. Produces a SongProfile.md with sourced gear breakdown, inventory-matched Applied section, and conversational follow-up prompts.
---

# patchbay:liner-notes

Research the rig and tone behind a song or artist.

**Before starting any research**, read these three reference files from the plugin root:
- `references/convention.md` — project paths, folder layout, slug rules
- `references/inventory.md` — how to read and normalize the user's owned gear
- `references/sources.md` — per-site fetch strategies

## Invocation patterns

Activate on any of these patterns:
- "Liner notes on [song] by [artist]"
- "Research the gear behind [song]"
- "What gear was used on [song] by [artist]"
- "Tell me what was used on [song]"
- "Get the sound of [song]"
- "/song [query]"

**Artist-only requests** ("the Bonham drum sound", "Jonny Greenwood's tone") — route to
`Artists/<Artist>/ArtistProfile.md` flow with broader scope (rig over time, not one recording).
Process is the same but target is `artists_root/<Artist>/ArtistProfile.md`.

## Process

### Step 1: Resolve target

Identify: artist display name, song title, year (if known).

Produce:
- `artist-display`: exactly as the user typed it (e.g., "Led Zeppelin")
- `song-slug`: title lowercased, spaces → hyphens, punctuation removed (e.g., "when-the-levee-breaks")
- `song-folder`: `<songs_root>/<artist-display>/<song-slug>/` per `references/convention.md`

**Ambiguous title** (common title, could be multiple artists or songs):
- List 2–4 candidates with artist, year, genre context
- Ask user to pick before proceeding
- Maximum 2 clarifying questions; if still unresolved, decline gracefully

### Step 2: Check for existing file

Check if `<song-folder>/SongProfile.md` exists.

**If it does**, present the re-run menu:
> "A SongProfile exists for [Song] by [Artist]. What would you like to do?
> 1. **Refresh** — re-fetch sources, update Research and Applied (your Corrections are untouched)
> 2. **Extend** — keep existing Research, add new angles or sources
> 3. **Leave it** — abort, no changes
> 4. **Start over** — wipe and re-run from scratch (your Corrections will be re-appended at the end)"

**Corrections are sacred.** Never delete or alter user-authored content under `## Corrections`.

If the file exists but appears corrupted (no frontmatter, unreadable structure):
- Refuse to overwrite
- Offer: "The file looks corrupted. I can back it up to SongProfile.md.bak and re-run — want me to do that?"

**If it doesn't exist**, proceed to Step 3.

### Step 3: Gather research

Follow strategies in `references/sources.md`. Attempt all six source types in order:
1. Equipboard
2. Premier Guitar
3. Sound on Sound
4. Tape Op
5. YouTube rig rundowns (via `add-youtube` CLI)
6. General web fallback

Create `<song-folder>/sources/` directory. Save each successful fetch as
`sources/<site>-<YYYY-MM-DD>.md` with required frontmatter.

If a source fetch fails: note it inline ("Equipboard: Cloudflare blocked — used web-search
fallback"); do not abort the run.

### Step 4: Detect track type

From gathered research, determine:

- **Traditional rig**: instruments, pedals, amps → continue normal flow
- **Sample-based / electronic**: no traditional guitar rig (most Daft Punk, DJ sets,
  sample-heavy hip-hop) → stop and reframe: "This track is sample-based / electronic —
  there isn't a traditional guitar rig to document. Want me to research the synthesizers,
  production techniques, or samples used instead?" Do not produce a SongProfile with
  fabricated guitar gear.
- **Found-object / experimental percussion** (Björk, Tom Waits, Stomp-style):
  continue normal flow. Note items as found-objects with technique descriptions in
  `## Research`. `## Applied` suggests household stand-ins. `## Gear Acquisition` typically empty.

### Step 5: Synthesize ## Research

Write a per-instrument or per-player-role breakdown.

For each instrument/role:
- List gear: `**[Item type]:** [Brand Model] (confidence: high/med/low — [source-file](sources/...))`
- Include signal chain if determinable from sources
- Surface conflicts explicitly: "Equipboard says Whammy II; Premier Guitar says Whammy IV — see Corrections to resolve."

**Citation rule: every gear claim must reference a source file.** No bare claims.
If you cannot find evidence for a claim, write: "not found in available sources."
No fabricated gear, ever.

### Step 6: Cross-reference inventory

Read inventory using `references/inventory.md`.

For each gear claim in `## Research`, match against inventory:
- **Exact**: brand + model
- **Category**: same subcategory, different brand/model
- **Generic**: same broad category

Produce a claim → inventory match map (internal; drives Step 7).

### Step 7: Build ## Applied

Prose signal chain using inventory matches:
- Exact match: "You own the [Item] — use it directly."
- Category match: "Your [Item] ([brand], same category) covers this role."
- Generic match: "Any [category] works here; your closest is [Item]."
- No match: "No [category] in your inventory — generic stand-in: any [category]."

**If inventory is empty**, prepend:
"No gear inventory found — results use generic substitutions. Run `patchbay:soundcheck`
to configure your folder layout, then `patchbay:add-gear` to add items."

Append `## Where next` with exactly 3 follow-up prompts, specific to this song:
- One asking for dial-in settings on a key pedal
- One asking for a cover-friendly / stripped-down version
- One creative "what if" swap or variation

### Step 8: Build ## Gear Acquisition

Determine GAS mode:
1. Per-call phrase "with GAS on" → on. "with GAS off" → off.
2. Otherwise read `patchbay.yml` `gas_mode` (default: false).

| GAS | Coverage | Render |
|---|---|---|
| Off | Inventory covers all meaningful categories | Omit section entirely |
| Off | Real gap (≥1 category has no owned match that meaningfully affects the sound) | One-line nudge: "GAS mode is off. To fully match this sound you'd need [category list] you don't currently own. Toggle GAS on for specifics." Cosmetic mismatches (slightly different fuzz model when user owns a fuzz) do NOT count as a real gap. |
| On | Any | Full section: read `Purge.md` (from `patchbay.yml` `purge_list`) for funded swaps + standalone acquisitions + wishlist additions, with reasoning per item. If Purge.md not found: standalone acquisitions only; note "No purge list found — run `patchbay:purge` to build one for funded swap suggestions." |

### Step 9: Apply corrections (re-run only)

If this is a re-run and `## Corrections` has user content:
- Re-read each correction entry; apply as an override to `## Research` and `## Applied`
- Correction wins over any new source: if new sources still say X but correction says Y,
  log the conflict: "(new sources say X; overridden by correction dated [date])"
- Re-append the corrections block verbatim at the end of the new SongProfile.md

### Step 10: Write SongProfile.md

Assemble the complete file. Create all parent directories as needed.
Update frontmatter fields: `last_researched`, `sources` list, `gas_mode`, `gear_referenced`.

Suggest a git commit message to the user:
```
feat: add liner notes for [Song] by [Artist]
```

## SongProfile.md format

```markdown
---
artist: <Artist Display Name>
song: <Song Title>
slug: <song-slug>
year: <year or null>
album: <album or null>
key: <key or null>
bpm: <bpm or null>
genres: [<genre>, ...]
last_researched: <YYYY-MM-DD>
last_corrected: null
gas_mode: <true|false>
sources:
  - <source-filename.md>
gear_referenced:
  - <artist-slug>/<member-slug>/<gear-slug>
---

# <Song> — <Artist>

## Research

### <Instrument/Role> (<Player Name>)
- **<Item type>:** <Brand Model> (confidence: high/med/low — [source-file](sources/source-file.md))
- Signal chain: ...

### <Next instrument/role>
...

### Sources
- [equipboard-YYYY-MM-DD.md](sources/equipboard-YYYY-MM-DD.md)
- [premier-guitar-YYYY-MM-DD.md](sources/premier-guitar-YYYY-MM-DD.md)

## Applied

<Prose signal chain using inventory matches. Generic substitutions where no match.>

## Where next
- *<Follow-up prompt 1 — dial-in settings for a specific pedal>*
- *<Follow-up prompt 2 — cover-friendly version>*
- *<Follow-up prompt 3 — creative what-if swap>*

## Corrections
<!-- User adds corrections here. This section is never touched by liner-notes on re-run. -->

## Gear Acquisition
<!-- GAS-gated. Omit entirely when GAS off and no real inventory gap. -->
```

## Failure mode reference

| Failure | Behavior |
|---|---|
| Disambiguation impossible | Decline gracefully after 2 clarifying questions |
| No sources found | Minimal SongProfile with note; no fabricated claims |
| Equipboard blocked | Web-search fallback; log inline in Sources |
| Inventory empty | Generic-only Applied with setup note |
| Corrupted SongProfile.md | Refuse overwrite; offer backup-and-rewrite |
| `add-youtube` not installed | Skip YouTube; note in ## Sources |
| WebFetch returns garbage | Skip source; note inline; don't poison synthesis |
| Correction vs new finding | Correction wins; log override note |
| GAS on, Purge.md missing | Standalone acquisitions only; recommend patchbay:purge |
| Artist-only request | Route to ArtistProfile.md flow (broader scope) |
| Sample-based / electronic track | Reframe; ask if user wants production/synth research instead |
| Found-object / experimental | Treat seriously; found-object technique notes in Research |
| `## Applied` inventory gap nudge | One-line GAS-off nudge for real gaps; silence for cosmetic ones |
