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
