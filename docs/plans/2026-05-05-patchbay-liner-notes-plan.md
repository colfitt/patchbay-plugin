# patchbay:liner-notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working `patchbay:liner-notes` Claude Code plugin skill that produces a sourced, inventory-aware SongProfile.md for any song a musician asks about.

**Architecture:** Vertical-slice — implement the minimum plugin scaffold and liner-notes-specific references in one pass rather than writing a plugin-level spec first. The skill is a SKILL.md instruction file backed by three plugin-level reference files (convention detection, inventory adapter, source strategies) and a patchbay.yml config template. No speculative scaffolding for skills not yet planned.

**Tech Stack:** Claude Code plugin system (SKILL.md + plugin.json + references/); Claude built-ins WebSearch + WebFetch; optional `add-youtube` Rust CLI (Pedalxly `rust-tools/`) for YouTube rig rundowns.

---

## Files created by this plan

| File | Responsibility |
|---|---|
| `.claude-plugin/plugin.json` | Plugin identity; required for Claude to load the plugin |
| `references/convention.md` | Folder detection, default paths, slug rules for Songs/ output |
| `references/inventory.md` | Inventory adapter: read Gear/*/GearProfile.md, normalize, match |
| `references/sources.md` | Per-site fetch strategies (Equipboard, PG, SoS, YouTube, web fallback) |
| `patchbay.yml.example` | Config template documenting all supported fields |
| `skills/liner-notes/SKILL.md` | The skill: invocation, process, output format, failure modes |
| `docs/testing/liner-notes-rehearsal.md` | Rehearsal script: golden tests, edge cases, inventory variants |

### Not created (no speculative scaffolding)

- Other skill stubs (`soundcheck`, `add-gear`, etc.) — each gets its own plan
- `Songs/` or `Artists/` folders in this repo — those live in user's project
- Shared `skills/` boilerplate beyond liner-notes

---

## Implementation decisions (review before executing)

**1. Artist folder naming:** Spec shows `Songs/Radiohead/creep/` — artist folder uses the display name as typed, song folder uses a lowercase hyphenated slug. This plan follows that. Override here if you want all-lowercase-slug paths.

**2. `gear_referenced` frontmatter slugs:** Spec shows `radiohead/jonny-greenwood/fender-telecaster`. These are forward-looking wiki links. This plan emits them in that format. They can be dropped if you want simpler frontmatter.

**3. `add-youtube` CLI:** Lives in Pedalxly's `rust-tools/`. Patchbay gracefully skips YouTube sources and notes the absence when it's not installed. No install doc in v1.

**4. Plugin install command:** Assumed to be `claude plugin install /path/to/patchbay-plugin` from the local repo. Not documented in plugin.json (distribution is out of scope per spec).

---

## Phase 1: Plugin manifest

### Task 1: Create `.claude-plugin/plugin.json`

**Files:**
- Create: `.claude-plugin/plugin.json`

- [ ] **Step 1: Create manifest**

```bash
mkdir -p .claude-plugin
```

Create `.claude-plugin/plugin.json`:

```json
{
  "name": "patchbay",
  "description": "A Claude Code plugin for musicians. Inventory your gear, research tones, design patches, and chase the sounds behind the songs you love.",
  "version": "0.1.0",
  "author": {
    "name": "colfitt",
    "email": "colfitt@gmail.com"
  },
  "license": "TBD",
  "keywords": ["music", "gear", "studio", "patches", "tone-research", "pedals"]
}
```

- [ ] **Step 2: Verify**

```bash
cat .claude-plugin/plugin.json
```

Expected: the JSON above, parseable, no syntax errors.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "feat: add plugin manifest (.claude-plugin/plugin.json)"
```

---

## Phase 2: Plugin-level references

### Task 2: Create `references/convention.md`

**Files:**
- Create: `references/convention.md`

- [ ] **Step 1: Create directory and file**

```bash
mkdir -p references
```

Create `references/convention.md`:

```markdown
# Patchbay: Folder Convention Detection

## Reading configuration

1. Look for `patchbay.yml` at the project root (the directory Claude was invoked from).
2. If found, parse it for path overrides. All fields are optional; defaults apply when absent.
3. If not found, use defaults.

## Default paths

| Purpose | Default | patchbay.yml key |
|---|---|---|
| Gear inventory root | `Gear/` | `gear_root` |
| Software inventory root | `Software/` | `software_root` |
| Song research output | `Songs/` | `songs_root` |
| Artist profiles | `Artists/` | `artists_root` |
| Purge/sell list | `Purge.md` | `purge_list` |

## Convention signals

A **Pedalxly-shaped** project:
- Has a `Gear/` folder whose immediate subdirectories are named `<Brand Model>/` (e.g., `Chase Bliss MOOD MkII/`)
- Each subfolder contains `GearProfile.md` with YAML frontmatter

A **minimal / custom** project: only `patchbay.yml` present, pointing at arbitrary paths.

A **flat** project: no structured gear folder. Treat as empty inventory.

If neither `Gear/` nor `patchbay.yml` is found: note "No gear inventory found" in Applied and recommend `patchbay:soundcheck`.

## Song output path

Song research writes to:
```
<songs_root>/<Artist Display Name>/<song-slug>/SongProfile.md
```

- **Artist folder:** the canonical display name, preserving capitalization as the user typed it.
- **Song slug:** lowercase, spaces → hyphens, punctuation removed.

Examples:
- "Creep" by Radiohead → `Songs/Radiohead/creep/SongProfile.md`
- "Black Hole Sun" by Soundgarden → `Songs/Soundgarden/black-hole-sun/SongProfile.md`
- "One More Time" by Daft Punk → `Songs/Daft Punk/one-more-time/SongProfile.md`
- "When the Levee Breaks" by Led Zeppelin → `Songs/Led Zeppelin/when-the-levee-breaks/SongProfile.md`

Create parent directories as needed when writing.
```

- [ ] **Step 2: Verify**

```bash
cat references/convention.md
```

Expected: full file, four example paths present, no placeholder text.

- [ ] **Step 3: Commit**

```bash
git add references/convention.md
git commit -m "feat: add references/convention.md (folder detection + path rules)"
```

---

### Task 3: Create `references/inventory.md`

**Files:**
- Create: `references/inventory.md`

- [ ] **Step 1: Write the file**

Create `references/inventory.md`:

```markdown
# Patchbay: Inventory Adapter

## Purpose

Produce a normalized list of owned gear for cross-referencing song research.
Only items with `status: owned` are included.

## How to read gear

1. Determine `gear_root` from `patchbay.yml`, or default to `Gear/`.
2. List immediate subdirectories of `gear_root`. Each is one gear item.
3. For each subdirectory, read `GearProfile.md`. Parse the YAML frontmatter block (content between `---` delimiters at the top of the file).
4. Extract: `name`, `brand`, `category`, `subcategory`, `status`, `tags`.
5. Include only items where `status: owned`.

Repeat for `software_root` (default `Software/`).

## GearProfile.md frontmatter shape (Pedalxly convention)

```yaml
---
name: MOOD MkII
brand: Chase Bliss
category: pedal
subcategory: looper-granular
status: owned          # owned | sold | wishlist | loaned | in-for-repair | broken
tags: []
---
```

## Normalized item shape (what the skill works with)

```yaml
brand: Chase Bliss
name: MOOD MkII
category: pedal          # pedal | software | synth | interface | keyboard | ...
subcategory: looper-granular
path: Gear/Chase Bliss MOOD MkII
tags: []
```

## Matching owned gear to song gear claims

Given a song gear claim (e.g., "DigiTech Whammy IV"), match against inventory at three levels:

| Level | Criteria | Example |
|---|---|---|
| **Exact** | brand + model match (case-insensitive, fuzzy ok) | "DigiTech Whammy IV" vs `brand: DigiTech, name: Whammy IV` |
| **Category** | same subcategory, different brand/model | "DigiTech Whammy" vs owned item with `subcategory: pitch-shifter` |
| **Generic** | same broad category | "tape echo" vs owned item with `subcategory: delay` |

Report the match level per claim. Unmatched = no inventory coverage for that claim.

## Empty inventory fallback

If `gear_root` does not exist and no `patchbay.yml` override is present:
- Do NOT error or abort.
- Continue with an empty owned-gear list.
- In `## Applied`, prepend: "No gear inventory found — results use generic substitutions. Run `patchbay:soundcheck` to configure your folder layout, then `patchbay:add-gear` to add items."
- Use generic category-level substitutions throughout (e.g., "any pitch-shifter" not a specific model).
```

- [ ] **Step 2: Verify**

```bash
cat references/inventory.md
```

Expected: full file, three match levels defined, empty fallback described.

- [ ] **Step 3: Commit**

```bash
git add references/inventory.md
git commit -m "feat: add references/inventory.md (gear inventory adapter + match levels)"
```

---

### Task 4: Create `references/sources.md`

**Files:**
- Create: `references/sources.md`

- [ ] **Step 1: Write the file**

Create `references/sources.md`:

```markdown
# Patchbay: Source Fetch Strategies

## General rules

- Save each fetched source to `<song-folder>/sources/<site>-<YYYY-MM-DD>.md`.
- Include frontmatter at top of each saved source file (see template below).
- Truncate body to 12,000 characters if larger; add a "... [truncated]" note.
- If a fetch fails or returns garbage HTML / binary / unrelated content: skip that source and note the skip inline. One bad source skipped > bad data included.
- Never let a single source failure abort the whole run.

## Source file frontmatter template

```yaml
---
url: <full URL>
fetched_at: <ISO 8601 datetime>
fetcher: <fetcher-name>
---
```

## Site strategies (highest confidence first)

### 1. Equipboard
Fetcher name: `equipboard-direct`

1. Construct URL: `https://equipboard.com/pros/<artist-slug>` where slug = artist name lowercased, spaces → hyphens (e.g., `jonny-greenwood`, `thom-yorke`).
2. `WebFetch` that URL.
3. If response is 403, Cloudflare challenge page, or CAPTCHA: fall back to `WebSearch "<artist> equipboard"` and WebFetch the top result URL.
4. Save as `sources/equipboard-<YYYY-MM-DD>.md`.

Signal: structured gear lists with brand/model. High confidence.

### 2. Premier Guitar
Fetcher name: `premier-guitar-rundown`

1. `WebSearch '"<artist>" "<song>" site:premierguitar.com'`
2. If no results: try `"<artist> rig rundown site:premierguitar.com"`.
3. `WebFetch` the top relevant result.
4. Save as `sources/premier-guitar-<YYYY-MM-DD>.md`.

Signal: rig rundown articles and video walkthroughs with hands-on gear detail.

### 3. Sound on Sound
Fetcher name: `sound-on-sound`

1. `WebSearch '"<artist>" "<song>" site:soundonsound.com'`
2. If no results: try `'"<artist>" site:soundonsound.com'`.
3. `WebFetch` top result.
4. Save as `sources/sound-on-sound-<YYYY-MM-DD>.md`.

Signal: "In The Studio" features and production breakdowns with recording context.

### 4. Tape Op
Fetcher name: `tapeop`

1. `WebSearch '"<artist>" site:tapeop.com'`
2. `WebFetch` top result.
3. Save as `sources/tapeop-<YYYY-MM-DD>.md`.

Signal: interview-format with detailed tracking / production notes. Occasionally vague on exact model numbers.

### 5. YouTube rig rundowns
Fetcher name: `youtube-rundown`

1. `WebSearch '"<artist>" "<song>" rig rundown site:youtube.com'` — or without `site:` filter if needed.
2. Identify top 2 YouTube video URLs from results.
3. For each: run `add-youtube <url>` (this CLI fetches the transcript and saves it as markdown).
4. Move or copy the output file into `sources/youtube-<video-id>-<YYYY-MM-DD>.md`.
5. **If `add-youtube` is not installed or errors:** skip YouTube sources entirely; append this note to `## Sources` in SongProfile.md:
   > "YouTube sources skipped — `add-youtube` CLI not installed. See Pedalxly `rust-tools/` for the tool."

### 6. General web fallback
Fetcher name: `web-fallback`

1. `WebSearch '"<artist>" "<song>" gear used recording signal chain'`
2. `WebFetch` top 2–3 results not already fetched above.
3. Save as `sources/web-<YYYY-MM-DD>.md` (combine multiple results into one file with a URL header per result).
4. Useful for: Reddit threads (r/guitarpedals, r/gearslutz), fan wikis, blog posts, interviews.

## Source priority / confidence

| Source | Confidence | Why |
|---|---|---|
| Equipboard | High | Structured musician-gear database |
| Premier Guitar | High | Journalist rig rundowns, hands-on |
| Sound on Sound | High | Detailed production features |
| Tape Op | Med–High | Interview-based; occasionally imprecise on model |
| YouTube rundowns | Med | Transcribed speech; imprecise at times |
| General web | Low–Med | Unvetted; useful for corroboration |

## Conflict handling

When two sources disagree on a gear claim, surface the conflict explicitly in `## Research`:

> "Pedal: DigiTech Whammy II ([equipboard-2026-05-05.md](sources/equipboard-2026-05-05.md)) vs. Whammy IV ([premier-guitar-2026-05-05.md](sources/premier-guitar-2026-05-05.md)) — see Corrections to resolve."

Do not pick a winner. Do not average. Let the user correct via `## Corrections`.
```

- [ ] **Step 2: Verify**

```bash
cat references/sources.md
grep "^### " references/sources.md
```

Expected: six `###` strategy headers present, conflict handling section present.

- [ ] **Step 3: Commit**

```bash
git add references/sources.md
git commit -m "feat: add references/sources.md (per-site fetch strategies)"
```

---

### Task 5: Create `patchbay.yml.example`

**Files:**
- Create: `patchbay.yml.example`

- [ ] **Step 1: Write the file**

Create `patchbay.yml.example` at the repo root:

```yaml
# patchbay.yml — project config for the patchbay Claude plugin
# Copy this file to patchbay.yml at your project root and adjust for your layout.
# All fields are optional; patchbay uses the defaults shown in comments when absent.

# Folder roots, relative to this file's directory.
gear_root: Gear           # default: Gear/
software_root: Software   # default: Software/
songs_root: Songs         # default: Songs/
artists_root: Artists     # default: Artists/

# Sell/purge list — read by liner-notes GAS mode to suggest funded swaps.
# If this file is missing, GAS mode shows standalone acquisitions only.
purge_list: Purge.md      # default: Purge.md

# GAS mode (Gear Acquisition Syndrome)
# false (default): optimize for substitution from existing gear
# true: surface honest acquisition options (new purchases + funded swaps from purge list)
# Override per-call with: "liner notes on Creep with GAS on"
gas_mode: false
```

- [ ] **Step 2: Verify**

```bash
cat patchbay.yml.example
```

Expected: all six fields present with comments, `gas_mode: false` at end.

- [ ] **Step 3: Commit**

```bash
git add patchbay.yml.example
git commit -m "feat: add patchbay.yml.example (user config template)"
```

---

## Phase 3: Rehearsal script (define success before writing the skill)

Write the rehearsal script now — before the skill — so we're clear on what "working" means. This is the closest thing to TDD available for instruction-based skills.

### Task 6: Create `docs/testing/liner-notes-rehearsal.md`

**Files:**
- Create: `docs/testing/liner-notes-rehearsal.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p docs/testing
```

- [ ] **Step 2: Write the rehearsal script**

Create `docs/testing/liner-notes-rehearsal.md`:

```markdown
# liner-notes Rehearsal Script

Manual rehearsal tests for `patchbay:liner-notes`. Run with Claude Code open in the
Pedalxly repo (`~/Dev/Pedalxly`). Re-run quarterly or after significant changes to SKILL.md.

## Setup

1. `cd ~/Dev/Pedalxly`
2. Install plugin (if not already): `claude plugin install ~/Dev/patchbay-plugin`
3. Launch Claude Code in that directory.

---

## Group 1: Golden test cases

These use Pedalxly's actual inventory (rich, hardware-heavy rig).

### 1.1 Creep — Radiohead (Whammy + ShredMaster)

Invocation:
> Liner notes on Creep by Radiohead

Expected behavior:
- Fetches Equipboard (or falls back to web search)
- Attempts all 6 source types from references/sources.md
- Creates `Songs/Radiohead/creep/SongProfile.md`
- Creates `Songs/Radiohead/creep/sources/` with ≥ 1 source file

Expected SongProfile.md structure:
- Frontmatter: `artist: Radiohead`, `song: Creep`, `year: 1992`
- `## Research` section present: mentions Jonny Greenwood, guitar, pitch device (Whammy)
- Every gear claim cites a source file — NO bare claims
- `## Applied` section: references at least one piece of Pedalxly gear by name
- `## Where next` sub-section: exactly 3 follow-up prompts
- `## Corrections` section: present, empty (comment only, untouched)
- `## Sources` section: lists source files with links

Verify with:
```bash
test -f Songs/Radiohead/creep/SongProfile.md && echo "PASS: file created" || echo "FAIL: file missing"
grep "## Research" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Research" || echo "FAIL"
grep "## Applied" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Applied" || echo "FAIL"
grep "## Where next" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Where next" || echo "FAIL"
grep "## Corrections" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Corrections" || echo "FAIL"
grep "## Sources" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Sources" || echo "FAIL"
ls Songs/Radiohead/creep/sources/ | wc -l   # expect ≥ 1
```

### 1.2 Black Hole Sun — Soundgarden (Leslie cab, baritone fuzz)

Invocation:
> Research the gear behind Black Hole Sun by Soundgarden

Expected:
- `Songs/Soundgarden/black-hole-sun/SongProfile.md` created
- `## Research` mentions Kim Thayil's guitar rig; rotary/Leslie effect if found in sources
- `## Applied` adapts to Pedalxly (no Leslie → suggests modulated reverb or vibrato sim)
- No invented gear

```bash
test -f "Songs/Soundgarden/black-hole-sun/SongProfile.md" && echo "PASS" || echo "FAIL"
```

### 1.3 One More Time — Daft Punk (sample-based / no traditional guitar rig)

Invocation:
> Liner notes on One More Time by Daft Punk

Expected:
- Skill detects from research that this is sample-based / synthesizer-based
- Reframes: does NOT produce a SongProfile.md with a fabricated guitar rig
- Response asks: "This track is sample-based / electronic — there isn't a traditional guitar rig. Want me to research the synthesizers, production techniques, or samples instead?"

```bash
# If a SongProfile.md was created, inspect it — there must be NO gear claims without sources
# and it should note the electronic/sample nature prominently
```

### 1.4 When the Levee Breaks — Led Zeppelin (room mic'd drums, found-object technique)

Invocation:
> What gear and recording setup was used on When the Levee Breaks by Led Zeppelin?

Expected:
- `Songs/Led Zeppelin/when-the-levee-breaks/SongProfile.md` created
- Research mentions John Bonham's kit and the Headley Grange stairwell room miking
- Found-object / room technique noted in `## Research` with technique description
- `## Applied` suggests household-stand-in ideas for the room sound
- `## Gear Acquisition` typically empty (you can't buy a stairwell)

```bash
test -f "Songs/Led Zeppelin/when-the-levee-breaks/SongProfile.md" && echo "PASS" || echo "FAIL"
```

### 1.5 Smells Like Teen Spirit — Nirvana (heavily documented, slash command)

Invocation:
> /song Smells Like Teen Spirit Nirvana

Expected:
- `/song` shorthand works identically to conversational invocation
- `Songs/Nirvana/smells-like-teen-spirit/SongProfile.md` created
- Research: Kurt Cobain's Fender Jaguar/Mustang, Boss DS-1/DS-2, Mesa Boogie amp
- Applied: matches against Pedalxly inventory — Pedalxly has fuzz + OD pedals; verify substitution logic fires

```bash
test -f "Songs/Nirvana/smells-like-teen-spirit/SongProfile.md" && echo "PASS" || echo "FAIL"
grep -i "DS-1\|DS-2\|distortion\|overdrive" "Songs/Nirvana/smells-like-teen-spirit/SongProfile.md" && echo "PASS: DS-1/2 noted" || echo "FAIL"
```

---

## Group 2: Edge cases (failure modes)

### 2.1 Ambiguous title

Invocation:
> Liner notes on Yesterday

Expected:
- Claude asks for clarification — "Yesterday" could be multiple songs
- Lists candidates with artist + year + genre
- Does NOT assume Beatles

### 2.2 No sources found (obscure track)

Use any very obscure track you know has zero gear documentation online.

Expected:
- Creates minimal SongProfile.md with note: "Limited sources found — no gear claims made. Ingest any interviews or gear info you have and re-run."
- Does NOT fabricate gear claims
- All `## Research` claims are explicitly marked "not found in available sources" if no source exists

### 2.3 Artist-only input

Invocation:
> Tell me about the Bonham drum sound

Expected:
- Routes to artist-level: mentions `Artists/Led Zeppelin/ArtistProfile.md` scope
- Does NOT try to match to a specific song

### 2.4 GAS mode on

Invocation:
> Liner notes on Creep by Radiohead with GAS on

Expected:
- `## Gear Acquisition` section is populated (not just a one-line nudge)
- Reads `Purge.md` if present; suggests funded swaps where items there cover cost of missing gear
- If Purge.md not present in Pedalxly: note "No purge list found. Run `patchbay:purge` to build one."

```bash
grep "## Gear Acquisition" Songs/Radiohead/creep/SongProfile.md && echo "section present" || echo "FAIL"
```

### 2.5 Re-run on existing SongProfile.md

Pre-condition: Test 1.1 must have run — `Songs/Radiohead/creep/SongProfile.md` exists.

Invocation:
> Liner notes on Creep by Radiohead

Expected:
- Skill detects the file exists
- Offers all four options: Refresh / Extend / Leave it / Start over
- Does NOT silently overwrite
- User picks "Leave it" → aborts cleanly with no file changes

### 2.6 Corrections are sacred

Pre-condition: Manually add a correction to `Songs/Radiohead/creep/SongProfile.md`:
```markdown
## Corrections
- 2026-05-05: The Whammy pedal was the II, not the IV. Confirmed from producer interview.
```

Run "Refresh" (re-run the skill on this file, pick option 1).

Expected:
- `## Corrections` block preserved verbatim — the correction is still there, unchanged
- `## Applied` section reflects the correction (Whammy II, not IV)
- `## Research` notes the conflict if sources still say Whammy IV

### 2.7 Empty inventory

Pre-condition:
```bash
cd ~/Dev/Pedalxly
mv Gear Gear.bak
```

Invocation (pick "Start over" if file already exists):
> Liner notes on Creep by Radiohead

Expected:
- `## Applied` opens with the empty-inventory note:
  "No gear inventory found — results use generic substitutions..."
- Uses category-level language: "any pitch-shifter", "any overdrive", "any amp"
- Does NOT crash or produce an error message

Restore:
```bash
mv ~/Dev/Pedalxly/Gear.bak ~/Dev/Pedalxly/Gear
```

---

## Group 3: Inventory variation parity

Same song (Creep), three inventory states, verify Applied adapts.

### 3.1 Rich inventory (Pedalxly as-is)

Run test 1.1. Applied section should name specific Pedalxly gear (e.g., Eventide H90 for pitch, JHS pedal for OD). Verify at least two specific gear items named.

### 3.2 Partial inventory

```bash
mkdir -p /tmp/gear-backup
mv ~/Dev/Pedalxly/Gear/Strymon* ~/Dev/Pedalxly/Gear/Chase* ~/Dev/Pedalxly/Gear/Hologram* /tmp/gear-backup/
```

Run: "Liner notes on Creep by Radiohead" (Start over if file exists).

Expected: Applied uses fewer specific names; at least one generic substitution appears (e.g., "any reverb", "any delay").

Restore:
```bash
mv /tmp/gear-backup/* ~/Dev/Pedalxly/Gear/
```

### 3.3 Empty inventory (see 2.7 above)

---

## Group 4: GAS toggle parity

Run same song twice — GAS off vs. GAS on — compare the `## Gear Acquisition` section.

```
Run A: Liner notes on Smells Like Teen Spirit by Nirvana
Run B: Liner notes on Smells Like Teen Spirit by Nirvana with GAS on
```

Use "Start over" for Run B so it's a fresh run with GAS on.

Expected:
- Run A: `## Gear Acquisition` either omitted entirely (if inventory covers all categories) or shows one-line nudge only
- Run B: `## Gear Acquisition` has a full gear list with per-item acquisition suggestions

---

## Pass/Fail criteria

Each test passes when ALL of:
- [ ] Expected file paths created at correct locations
- [ ] All required `##` sections present in SongProfile.md
- [ ] No fabricated gear claims (every claim in `## Research` cites a `sources/` file)
- [ ] `## Corrections` block untouched on re-run
- [ ] Failure modes produce graceful prose messages, not stack traces or silently wrong output
- [ ] GAS on/off toggle changes `## Gear Acquisition` as specified
- [ ] Inventory empty → generic-only Applied with setup note
```

- [ ] **Step 3: Commit**

```bash
git add docs/testing/liner-notes-rehearsal.md
git commit -m "test: add liner-notes rehearsal script (golden cases + edge cases)"
```

---

## Phase 4: liner-notes skill

### Task 7: Create `skills/liner-notes/SKILL.md`

The implementation. Rehearsal script from Task 6 defines what it must produce.

**Files:**
- Create: `skills/liner-notes/SKILL.md`

- [ ] **Step 1: Create directory**

```bash
mkdir -p skills/liner-notes
```

- [ ] **Step 2: Write SKILL.md**

Create `skills/liner-notes/SKILL.md`:

```markdown
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
```

- [ ] **Step 3: Verify the file**

```bash
wc -l skills/liner-notes/SKILL.md
grep "^## " skills/liner-notes/SKILL.md
```

Expected output includes: `## Process`, `## SongProfile.md format`, `## Failure mode reference`.

- [ ] **Step 4: Commit**

```bash
git add skills/liner-notes/SKILL.md
git commit -m "feat: add skills/liner-notes/SKILL.md"
```

---

## Phase 5: Run rehearsal tests

### Task 8: Execute rehearsal against Pedalxly

Steps are **manual** — run them in Claude Code with `~/Dev/Pedalxly` as the working directory.

- [ ] **Step 1: Install plugin**

In a terminal (not inside Claude):
```bash
claude plugin install ~/Dev/patchbay-plugin
```

If the command fails or the plugin format has changed, check `claude plugin --help` for the current install syntax.

- [ ] **Step 2: Run golden test 1.1 (Creep)**

Open Claude Code in `~/Dev/Pedalxly`. Invoke:
> Liner notes on Creep by Radiohead

Then verify in terminal:
```bash
test -f Songs/Radiohead/creep/SongProfile.md && echo "PASS: file created" || echo "FAIL: file missing"
grep "## Research" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Research" || echo "FAIL"
grep "## Applied" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Applied" || echo "FAIL"
grep "## Where next" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Where next" || echo "FAIL"
grep "## Corrections" Songs/Radiohead/creep/SongProfile.md && echo "PASS: Corrections" || echo "FAIL"
ls Songs/Radiohead/creep/sources/ | wc -l   # expect ≥ 1
```

- [ ] **Step 3: Run golden test 1.3 (Daft Punk — sample detection)**

> Liner notes on One More Time by Daft Punk

Expected: reframe response, not a SongProfile.md with fabricated guitar gear.

```bash
# if a file was created, inspect it
test -f "Songs/Daft Punk/one-more-time/SongProfile.md" && cat "Songs/Daft Punk/one-more-time/SongProfile.md" || echo "No file created (expected if skill declined)"
```

- [ ] **Step 4: Run edge case 2.1 (ambiguous title)**

> Liner notes on Yesterday

Expected: clarification question listing candidates. Does NOT assume Beatles.

- [ ] **Step 5: Run edge case 2.4 (GAS on)**

> Liner notes on Smells Like Teen Spirit by Nirvana with GAS on

```bash
grep "## Gear Acquisition" "Songs/Nirvana/smells-like-teen-spirit/SongProfile.md" && echo "PASS: section present" || echo "FAIL"
```

- [ ] **Step 6: Run edge case 2.5 (re-run)**

Pre-condition: Creep file exists from Step 2.

> Liner notes on Creep by Radiohead

Expected: 4-option re-run menu appears. Pick "Leave it" → no file changes.

- [ ] **Step 7: Run edge case 2.7 (empty inventory)**

```bash
cd ~/Dev/Pedalxly && mv Gear Gear.bak
```

In Claude Code (pick "Start over" if Creep file exists):
> Liner notes on Creep by Radiohead

Check Applied section starts with the empty-inventory note and uses generic substitutions.

Restore:
```bash
mv ~/Dev/Pedalxly/Gear.bak ~/Dev/Pedalxly/Gear
```

- [ ] **Step 8: Log failures and fix**

For each failed check:
1. Identify which reference file or SKILL.md section produced the wrong behavior.
2. Edit that file to correct the instruction.
3. Re-run the failing test case.
4. Commit with: `fix: [description] in [file]`

---

## Spec coverage self-review

| Spec requirement | Implemented in |
|---|---|
| Conversational invocation + /song shorthand | Task 7 SKILL.md — Invocation patterns |
| Disambiguation flow | Task 7 Step 1 |
| Re-run flow (4 options) | Task 7 Step 2 |
| Corrections are sacred | Task 7 Steps 2 + 9 |
| GAS mode resolution (per-call → yml → default) | Task 7 Step 8 |
| All 6 source types (Equipboard, PG, SoS, Tape Op, YouTube, web) | Task 4 sources.md + Task 7 Step 3 |
| Track type detection (sample-based, found-object) | Task 7 Step 4 |
| Per-instrument Research synthesis + citations | Task 7 Step 5 |
| No fabricated gear | Task 7 Step 5 (citation rule) |
| Inventory cross-reference (3-level match) | Task 3 inventory.md + Task 7 Step 6 |
| Applied section with prose + Where next | Task 7 Step 7 |
| Gear Acquisition GAS table (3 rows) | Task 7 Step 8 |
| SongProfile.md full format + frontmatter | Task 7 SongProfile.md format section |
| All 13 failure modes from spec | Task 7 Failure mode reference |
| Folder convention detection + slug rules | Task 2 convention.md |
| Inventory adapter + empty fallback | Task 3 inventory.md |
| patchbay.yml schema (all fields) | Task 5 patchbay.yml.example |
| Golden test cases (Creep, BHS, Daft Punk, Levee, Teen Spirit) | Task 6 Group 1 + Task 8 |
| Edge cases (ambiguous, no sources, GAS, re-run, corrections, empty) | Task 6 Group 2 + Task 8 |
| Inventory variations (rich, partial, empty) | Task 6 Group 3 |
| GAS toggle parity | Task 6 Group 4 |

No gaps found. All spec requirements are covered.
