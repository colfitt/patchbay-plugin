# Phase 2 — Plan 02: Skill body (`patchbay-ingest`)

**Phase:** 2 (Chunk schema + patchbay:ingest)
**Plan:** 02 of 03
**Wave:** 2
**Depends on:** Plan 01 (schema reference + image-category enum must exist; SKILL.md links to them)
**Autonomous:** yes

---

## Goal

Author the production skill end-to-end so that running `/patchbay:ingest <gear>` against a real manual PDF produces a populated, schema-valid `chunks.jsonl`. Re-running the skill on the same gear shows a diff and preserves user-edited chunks.

**Observable outcome:** `skills/patchbay-ingest/SKILL.md` exists, has valid frontmatter (`name`, `description`), activates on the documented invocation patterns, and contains all seven process steps with the diff-on-reingest preservation logic explicitly specified.

---

## Files to create

- `skills/patchbay-ingest/SKILL.md` (new — the deliverable)

## Files NOT to create / modify

- Do not modify `skills/patchbay-ingest/references/chunk-schema.md` or `image-categories.md` — owned by Plan 01.
- Do not create example `chunks.jsonl` files in this repo. The skill produces them at runtime under the user's `<gear_root>/<Brand Item>/knowledge/`. Phase 2 ships the skill, not example data.
- Do not edit `skills/dialed-in/SKILL.md` or `skills/liner-notes/SKILL.md` — they are reference shapes only.

---

## Concrete steps

### Step 1: Read reference shapes

Re-read all three to internalize the canonical patchbay-skill voice and structure:
- `skills/liner-notes/SKILL.md` (the original; longest-established voice)
- `skills/dialed-in/SKILL.md` (most recent; canonical Phase-1-validated shape)
- `skills/patchbay-ingest/references/chunk-schema.md` (Plan 01's output — load-bearing)
- `skills/patchbay-ingest/references/image-categories.md` (Plan 01's output)

Also read for context (do not duplicate verbatim; cite/link instead):
- `references/convention.md` (for `gear_root` + folder layout)
- `references/inventory.md` (for resolving `<gear>` arg → `<Brand Item>` folder)
- `.claude/skills/spike-findings-patchbay-plugin/references/manual-ingestion.md` (the production blueprint — pipeline, anti-patterns, constraints)
- `.planning/REQUIREMENTS.md` § INGEST-01..06

### Step 2: Write SKILL.md frontmatter + intro

```yaml
---
name: patchbay-ingest
description: Ingest a gear manual PDF into the per-gear knowledge store as schema-valid chunks. Activates on "ingest manual for [gear]", "ingest [gear] manual", "/patchbay:ingest [gear]", and as a follow-up after add-gear when a manual is present.
---
```

Then a one-line title (`# patchbay:ingest`), a one-paragraph purpose, and the "Before starting" pointer block matching the dialed-in / liner-notes shape:

> **Before starting any ingest**, read these reference files:
> - `references/convention.md` (plugin root) — gear folder layout, `patchbay.yml` resolution
> - `references/inventory.md` (plugin root) — owned-gear normalization
> - `skills/patchbay-ingest/references/chunk-schema.md` — load-bearing chunk shape (every chunk you write must conform)
> - `skills/patchbay-ingest/references/image-categories.md` — the seven-value `image_category` enum

### Step 3: Invocation patterns section

```
"Ingest manual for [gear]"                        → resolve gear, locate manual(s), confirm, ingest
"Ingest [gear] manual"                            → same routing
"/patchbay:ingest [gear]"                         → same routing
"/patchbay:ingest"                                → no gear arg → list owned gear with manuals; ask user which
```

Plus a follow-up handoff note: "If invoked in the same session as `add-gear` and a manual was just dropped into the gear folder, the manual path is already in context — skip the resolve step and go directly to confirm." (Mirrors the liner-notes follow-up pattern.)

### Step 4: Process — eight steps

Each step has a heading (`### Step N: <verb phrase>`) and prose. Maintain the dialed-in voice (terse, specific, exact strings where the user-facing message matters).

#### Step 1: Resolve gear → manual path

1. Parse `<gear>` arg (or prompt if missing). Normalize via `references/inventory.md` rules (case-insensitive brand+name matching).
2. Resolve `gear_root` from `patchbay.yml` (default `Gear/`).
3. Target folder: `<gear_root>/<Brand Item>/`. If folder does not exist, stop:
   > "No gear folder found for [gear]. Run `patchbay:add-gear` first, or check that your folder name matches `<Brand> <Item>`."
4. Manual path(s): `<gear_root>/<Brand Item>/manuals/*.pdf`. If `manuals/` empty or missing, stop:
   > "No manual PDF found for [gear] at `<gear_root>/<Brand Item>/manuals/*.pdf`. Drop a PDF in that folder and re-run, or pick a different gear."
5. If multiple PDFs, present a numbered list and ask user to pick (or accept `all` for sequential ingest of each — one at a time, not parallel).

#### Step 2: Check existing chunks

Check whether `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` exists.

- **If absent:** create the `knowledge/` directory; proceed to Step 3 (fresh ingest path).
- **If present:** read every line, parse as JSON, build an in-memory map `{ chunk_id → chunk }`. Note this is a re-ingest run — Step 7 (diff) applies.

#### Step 3: Plan batches

Use the Read tool to determine PDF page count (open with no `pages` argument first, or query metadata). Plan batches:
- 1–20 pages: one Read call (`pages: "1-20"` or `"1-N"`).
- 21+ pages: sequential calls of 20-page windows: `1-20`, `21-40`, `41-60`, ...
- Last batch absorbs remainder (e.g., 67-page manual: `1-20`, `21-40`, `41-60`, `61-67`).

Record the batch plan and announce to user before starting:
> "Manual has [N] pages. Ingesting in [M] batches of up to 20 pages. This may take several minutes."

#### Step 4: Read each batch + produce chunks per page

For each batch, call the Read tool with `pages: "<start>-<end>"` against the absolute manual path.

For each rendered page in the batch, produce 1–4 chunks split by content block. Apply these splitting rules (from spike 001, manual-ingestion blueprint):

- **One text chunk per logical text block** — section heading + its body paragraphs become one `text` chunk. A page with two distinct sections produces two text chunks.
- **One image chunk per image** — every image becomes an `image` chunk; categorize against the seven-value enum from `image-categories.md`. **No filtering, including marketing covers.**
- **Page with only an image (e.g. cover, full-page diagram):** one `image` chunk, no text chunk.
- **Page with only text:** one or more `text` chunks per logical block.
- **Page with mixed content:** combine — typically 1 text chunk + 1 image chunk = 2 chunks; up to 4 if multiple sections + multiple images.
- **Image-category fit:** if an image does not cleanly fit any of the seven categories, choose the closest match AND set `_low_confidence_category: true` on the chunk; collect these for end-of-run review (per `image-categories.md` edge-case rule).

Each chunk must conform to `references/chunk-schema.md` § Required fields. Chunk-ID format:
- Text: `p<NNN>-c<NN>` (e.g., `p016-c01` for page 16, chunk 1)
- Image: same scheme; chunks numbered in reading order top-to-bottom on the page
- Provenance fields are mandatory: `manual` (filename), `page` (int), `rough_region` (`top` / `middle` / `bottom` / `full-page`), `scraped_at` (ISO date — set once at start of run).

Do not summarize. Preserve verbatim text from the manual; describe images literally (panel-diagrams: enumerate every numbered callout).

#### Step 5: Batch boundary continuity check

After each batch, verify the last page of the previous batch and first page of the current batch are both present in chunk output (no gap). If a section spans the boundary (e.g., a heading on page 20 with body continuing on page 21), each page still gets its own chunks — do not bundle across pages. The chunk IDs (p020-cNN, p021-cNN) preserve the relationship; downstream consumers can stitch.

This satisfies INGEST-03 (Read-tool batching with no gaps).

#### Step 6: Write or diff `chunks.jsonl`

**Fresh ingest (Step 2 found no existing file):**
1. For each chunk produced in Step 4, append one JSON-encoded line to `<gear_root>/<Brand Item>/knowledge/chunks.jsonl`.
2. JSON encoding: minified single-line per chunk; UTF-8; trailing newline; no trailing comma.
3. Order: chunks written in the order produced (page order, chunk-within-page order).
4. Confirm to user: "Wrote [N] chunks to `[path]`."

**Re-ingest (Step 2 loaded an existing map):**

Diff is mandatory before any write (INGEST-05 + INGEST-06).

For each newly-produced chunk:
- **New ID** (no match in existing map): mark `+ added`.
- **Existing ID, same content** (`content` field deep-equals): mark `= unchanged`.
- **Existing ID, different content, no `_user_edited` flag**: mark `~ updated` (the model produced a different description this run).
- **Existing ID, different content, `_user_edited: true` set on the existing chunk**: mark `! preserved` — DO NOT overwrite. The user has corrected this chunk; the new model output is shown for comparison only.

For each existing chunk with no match in the new run:
- mark `- removed` (suggests the page no longer parses to a chunk in that slot).

Present the diff to the user as a summary:
> "Re-ingest diff for [gear]:
>   + [X] new chunks
>   ~ [Y] updated (model output changed)
>   ! [Z] preserved (you edited these — not overwriting)
>   = [W] unchanged
>   - [V] removed
>
> Confirm to write? (yes / show details / cancel)"

If user picks `show details`, list each ~ / ! / − chunk by ID with a one-line content delta. Then re-prompt.

On `yes`: write a new `chunks.jsonl` containing:
- All `+ added` chunks
- All `~ updated` chunks (new content)
- All `! preserved` chunks (existing content, with `_user_edited: true` retained)
- All `= unchanged` chunks (existing content)
- `- removed` chunks are dropped

Back up the prior file to `chunks.jsonl.bak` before overwriting, in case the user wants to undo.

On `cancel`: leave `chunks.jsonl` untouched. Suggest `patchbay:ingest --review` (future sub-command, out of scope this phase) for selective merging.

#### Step 7: User-edit preservation contract

Document explicitly inside the SKILL.md (not just as a step) so users know how to mark edits:

> **How to preserve a chunk through re-ingest:** Edit the chunk's `content` directly in `chunks.jsonl` (or in a per-chunk markdown export — future feature) AND add `"_user_edited": true` to the chunk. On the next `/patchbay:ingest` run for that gear, the diff marks your edited chunk `! preserved` and never overwrites it. The flag persists across re-ingests until you remove it.

This is the load-bearing satisfier for INGEST-06 — corrections survive re-ingest because the skill explicitly checks `_user_edited` before overwriting.

#### Step 8: Closeout

After write:
1. Report low-confidence image categories collected during Step 4. List them by chunk ID and prompt:
   > "[N] images had ambiguous categories — review and re-categorize manually if needed: [chunk-ids]"
2. Suggest a git commit:
   > `feat: ingest [Brand Item] manual ([N] chunks)`
3. If invoked in a session where the user is likely to ingest more gear, offer: "Want to ingest another manual? List remaining gear with manuals: ..."

### Step 5: Error-handling table

Standard 8-row table matching the dialed-in shape. Required rows:

| Situation | Behavior |
|---|---|
| No gear folder for `<gear>` | Stop. Direct user to `patchbay:add-gear` |
| `manuals/` missing or empty | Stop. Tell user to drop a PDF in `<gear_root>/<Brand Item>/manuals/` |
| Multiple PDFs in `manuals/` | Numbered picker; accept index, multiple, or `all` (sequential) |
| Read tool fails on a batch | Retry once; if still failing, log the page range, skip that batch, continue. Surface skipped ranges at end. Do not abort the whole run. |
| Image does not fit any of the seven categories | Use closest match + set `_low_confidence_category: true`; collect for end-of-run review |
| Re-ingest, user picks `cancel` at diff | Leave `chunks.jsonl` untouched; `chunks.jsonl.bak` is not written |
| `chunks.jsonl` is corrupt (un-parseable lines) on re-ingest | Refuse to overwrite; offer to back up to `chunks.jsonl.corrupt.bak` and proceed as fresh ingest |
| Scanned PDF with no embedded text (vision-only) | Proceed; flag the run with a warning that text-chunk content may be OCR-quality only; user can correct via the `_user_edited` flag |

### Step 6: UI layer notes section

Required (per the always-include-UI-notes feedback rule). Format matches dialed-in's `## UI layer notes` section. Required rows:

| Decision | UI implication |
|---|---|
| Append-only JSONL, one chunk per line | UI streams chunks page-by-page; no need to load full file |
| Chunk-ID encodes page + sequence (`p016-c04`) | UI can render chunks in manual reading order without inspecting content |
| `provenance.rough_region` ∈ four values | UI highlights a quadrant of the source page on hover — no bounding box needed for v1 |
| `image_category` ∈ closed seven-value enum | UI renders category-specific affordances (panel-diagram → callout overlay; marketing → de-emphasize; screen-screenshot → state-aware tile) |
| `_user_edited: true` flag | UI shows a "you edited this" badge; prevents accidental overwrite via UI re-ingest button |
| `_low_confidence_category: true` flag | UI shows a "needs review" badge; clicking it presents the seven categories as a picker |
| Diff-on-reingest with explicit categories (`+ ~ ! = -`) | UI maps directly to a per-chunk diff list with checkboxes — same surface a CLI-level user sees |
| `chunks.jsonl.bak` backup before re-ingest write | UI offers an "undo last ingest" button that restores from `.bak` |

End the section with a one-line load-bearing-decision callout:

> **The diff-on-reingest preservation flag (`_user_edited`) is the most load-bearing UI decision in this phase.** It is the contract between the user's manual corrections and the skill's automation. Both CLI and UI re-ingest paths key off this single field; both must honor it identically.

### Step 7: Self-check against requirements

Before declaring done, verify each INGEST requirement and each Phase 2 success criterion has a clear locus in SKILL.md. Walk this list:

- INGEST-01 (`/patchbay:ingest <gear>` populates `chunks.jsonl`) → § Process Step 1 + Step 6
- INGEST-02 (every image → chunk; seven-value enum; no filtering) → § Process Step 4 + linked `image-categories.md`
- INGEST-03 (multi-page batching, no gaps) → § Process Step 3 + Step 5
- INGEST-04 (1–4 chunks per page split by content block) → § Process Step 4 splitting rules
- INGEST-05 (re-ingest diff + confirm) → § Process Step 6 re-ingest path
- INGEST-06 (user-edited chunks survive re-ingest) → § Process Step 6 (`! preserved` rule) + § Process Step 7 (`_user_edited` contract)
- Success criterion 6 (additive fields, no schema break) → already anchored in Plan 01's schema doc; SKILL.md links to it.

---

## Verification

Plan succeeds when **all** of these are true:

1. `skills/patchbay-ingest/SKILL.md` exists.
2. The file parses as valid markdown with valid YAML frontmatter (`name: patchbay-ingest`, `description: ...`).
3. The skill body contains every required section: intro, Before-starting pointer, Invocation patterns, Process (Steps 1–8), Error-handling table (≥8 rows), UI layer notes table.
4. Process Step 6 specifies the five diff categories (`+ added`, `~ updated`, `! preserved`, `= unchanged`, `- removed`) and the user-confirm gate before write.
5. Process Step 7 documents the `_user_edited: true` contract (the user-edit preservation rule).
6. Every INGEST requirement (INGEST-01..06) has a clear locus (verifiable by reading the SKILL.md against the checklist in Step 7 above).
7. Voice and structure visibly match `skills/dialed-in/SKILL.md` (frontmatter shape, "Before starting" block, numbered Process steps, error-handling table, UI layer notes).
8. The two reference docs from Plan 01 are linked at least once each (`references/chunk-schema.md` and `references/image-categories.md`).

**Manual sanity check** (five minutes): grep for the load-bearing exact strings (the user-facing messages in Step 1, Step 6 diff prompt, Step 7 contract). Confirm wording is committed.

---

## Requirements covered

- **INGEST-01** — `/patchbay:ingest <gear>` populates `chunks.jsonl`
- **INGEST-02** — All images become image chunks with seven-value `image_category`; no filtering
- **INGEST-03** — Multi-page PDFs handled via 20-page Read-tool batching, no gaps
- **INGEST-04** — Each page produces 1–4 chunks split by content block
- **INGEST-05** — Re-ingest shows a diff and asks to confirm before overwriting
- **INGEST-06** — User-edited chunks survive re-ingest (via `_user_edited` flag)

---

## Out of scope for Plan 02

- Per-chunk markdown export (mentioned in INGEST-06 as an *alternative* edit surface; v1 ships JSONL-edit only — markdown export is a follow-up if user demand emerges)
- A `patchbay:ingest --review` sub-command for selective merge during diff (called out in Step 6 cancel branch as a future follow-up)
- Cross-source corroboration (`cross_source_match_candidates`) — Phase 3 territory
- Citation-target population — Phase 4 territory
- Real end-to-end test against a user's manual (Plan 03)
- A `chunks.jsonl` linter / validator script — referenced in chunk-schema.md but not built; runtime conformance is enforced by the skill itself

---

## UI layer notes

Captured inline within SKILL.md § UI layer notes (above). The plan-level UI-notes contract is satisfied by writing that section into the skill itself, where it travels with the deliverable forever.
