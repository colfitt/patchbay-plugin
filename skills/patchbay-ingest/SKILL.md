---
name: patchbay-ingest
description: Ingest a gear manual PDF into the per-gear knowledge store as schema-valid chunks. Activates on "ingest manual for [gear]", "ingest [gear] manual", "/patchbay:ingest [gear]", and as a follow-up after add-gear when a manual is present.
---

# patchbay:ingest

Turn a gear manual PDF into a populated, schema-valid `chunks.jsonl` for that gear. The chunks are gear-anchored, provenance-preserving, and citation-hover ready — the backbone source class for everything `patchbay:research` and the future conversational AI build on top of.

**Before starting any ingest**, read these reference files:
- `references/convention.md` (plugin root) — gear folder layout, `gear_root` resolution from `patchbay.yml`
- `references/inventory.md` (plugin root) — owned-gear normalization, how to resolve a `<gear>` arg against `<Brand Item>` folders
- `skills/patchbay-ingest/references/chunk-schema.md` — load-bearing chunk shape (every chunk you write conforms)
- `skills/patchbay-ingest/references/image-categories.md` — the seven-value `image_category` enum

## Invocation patterns

Activate on any of these patterns:

```
"Ingest manual for [gear]"        → resolve gear, locate manual(s), confirm, ingest
"Ingest [gear] manual"            → same routing
"/patchbay:ingest [gear]"         → same routing
"/patchbay:ingest"                → no gear arg → list owned gear with manuals; ask user to pick
```

**Follow-up from `add-gear`:** if invoked in the same session as a recent `patchbay:add-gear` run and a manual was just dropped into the gear folder, the manual path is already in context — skip the resolve step and go directly to confirm.

## Process

### Step 1: Resolve gear → manual path

1. Parse the `<gear>` arg (or prompt if missing). Normalize via `references/inventory.md` rules (case-insensitive brand+name matching, three-level fallback if needed).
2. Resolve `gear_root` from `patchbay.yml` (default `Gear/`).
3. Target folder: `<gear_root>/<Brand Item>/`. If the folder does not exist, stop:

   > "No gear folder found for [gear]. Run `patchbay:add-gear` first, or check that your folder name matches `<Brand> <Item>` (e.g., `Chase Bliss MOOD MkII`)."

4. Manual path(s): `<gear_root>/<Brand Item>/manuals/*.pdf`. If `manuals/` is missing or empty, stop:

   > "No manual PDF found for [gear] at `<gear_root>/<Brand Item>/manuals/*.pdf`. Drop a PDF in that folder and re-run, or pick a different gear."

5. If multiple PDFs are present, present a numbered list and ask the user to pick one (or accept `all` for sequential ingest of each — one at a time, never parallel).

### Step 2: Check for existing chunks

Check whether `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` exists.

- **If absent:** create the `knowledge/` directory; proceed to Step 3 (fresh ingest path).
- **If present:** read every line, parse each as JSON, build an in-memory map `{ chunk_id → chunk }`. Note this is a re-ingest run — Step 6's diff logic applies before any write.

If any line fails to parse (corrupt file), see the error-handling table — do not silently overwrite.

### Step 3: Plan batches

Determine the manual's page count. Open with the Read tool to get the count (or via PDF metadata). Plan batches:

- **1–20 pages:** one Read call with `pages: "1-N"`.
- **21+ pages:** sequential 20-page windows — `1-20`, `21-40`, `41-60`, … — with the last batch absorbing the remainder (e.g., 67-page manual splits as `1-20`, `21-40`, `41-60`, `61-67`).

Announce the plan to the user before starting:

> "Manual has [N] pages. Ingesting in [M] batches of up to 20 pages. This may take several minutes."

Record `scraped_at` ONCE at this point as an ISO 8601 timestamp; every chunk produced in this run carries the same value.

### Step 4: Read each batch + produce chunks per page

For each batch, call the Read tool with `pages: "<start>-<end>"` against the absolute manual path. Claude sees rendered page images plus OCR text natively — no separate vision pipeline needed.

For each rendered page, produce **1–4 chunks split by logical content block**:

- **One `text` chunk per logical text block** — a section heading plus its body paragraphs become one chunk. A page with two distinct sections produces two text chunks.
- **One `image` chunk per image** — every image becomes a chunk, categorized against the seven-value enum from `references/image-categories.md`. **No filtering, including marketing covers.**
- **Page with only an image** (e.g., cover, full-page diagram): one `image` chunk, no text chunk.
- **Page with only text:** one or more `text` chunks per logical block.
- **Page with mixed content:** typically 1 text + 1 image = 2 chunks; up to 4 if multiple sections or multiple images.
- **Image-category fit:** if an image does not cleanly match any of the seven categories, choose the closest match AND set `_low_confidence_category: true` on the chunk. Collect these for end-of-run review (per `image-categories.md` § Edge-case rule). Do not invent a new category.

Every chunk must conform to `references/chunk-schema.md` § Required fields. Concrete shape:

- **Chunk ID** (Step 4 produces one ID per chunk): `p<NNN>-c<NN>` — `p016-c01` for page 16, chunk 1. Chunks are numbered top-to-bottom in reading order on each page.
- **`provenance` block** (mandatory): `manual` (filename), `page` (1-indexed int), `rough_region` (`top` / `middle` / `bottom` / `full-page`), `scraped_at` (the run timestamp from Step 3).
- **`source`**: `"manual"`.
- **`content`**: a string for `text` chunks (markdown), an object `{ image_category, description }` for `image` chunks.

**Do not summarize.** Preserve verbatim text from the manual. For images: describe literally — for panel-diagrams, **enumerate every numbered callout** (the labels are on-image and won't appear in surrounding paragraphs).

### Step 5: Batch boundary continuity check

After each batch, verify the last page of the previous batch and the first page of the current batch are both represented in chunk output (no gap). If a section spans a boundary (e.g., a heading on page 20 with body continuing on page 21), each page still gets its own chunks — do not bundle across pages. The chunk IDs (`p020-cNN`, `p021-cNN`) preserve the relationship; downstream consumers stitch.

This satisfies INGEST-03 (multi-page batching, no gaps where Read-tool boundaries fall).

### Step 6: Write or diff `chunks.jsonl`

**Fresh ingest** (Step 2 found no existing file):

1. For each chunk produced in Step 4, append one JSON-encoded line to `<gear_root>/<Brand Item>/knowledge/chunks.jsonl`.
2. JSON encoding: minified single-line per chunk; UTF-8; newline-terminated; no trailing comma.
3. Order: chunks written in production order (page order, then chunk-within-page order).
4. Confirm to user: "Wrote [N] chunks to `[path]`."

**Re-ingest** (Step 2 loaded an existing map):

Diff is mandatory before any write. For each chunk produced this run, classify against the existing map:

| Category | Meaning |
|---|---|
| `+ added` | New ID — no match in the existing map. |
| `~ updated` | Existing ID, different `content`, no `_user_edited` flag. The model produced a different description this run. |
| `! preserved` | Existing ID, different `content`, `_user_edited: true` set on the existing chunk. **DO NOT overwrite.** New model output is shown for comparison only. |
| `= unchanged` | Existing ID, `content` deep-equals the existing chunk. |
| `- removed` | Existing chunk has no match in this run (the page no longer parses to a chunk in that slot). |

Present the diff to the user as a summary:

> "Re-ingest diff for [gear]:
>   + [X] new chunks
>   ~ [Y] updated (model output changed)
>   ! [Z] preserved (you edited these — not overwriting)
>   = [W] unchanged
>   − [V] removed
>
> Confirm to write? (yes / show details / cancel)"

If the user picks `show details`, list each `~` / `!` / `−` chunk by ID with a one-line content delta. Then re-prompt.

On `yes`:
1. Back up the prior file to `chunks.jsonl.bak` before overwriting (in case the user wants to undo).
2. Write a new `chunks.jsonl` containing: all `+ added` chunks, all `~ updated` chunks (new content), all `! preserved` chunks (existing content, with `_user_edited: true` retained), all `= unchanged` chunks (existing content). `- removed` chunks are dropped.

On `cancel`: leave `chunks.jsonl` untouched; do not write `chunks.jsonl.bak`. Suggest a future `patchbay:ingest --review` sub-command for selective merging (out of scope this phase).

### Step 7: User-edit preservation contract

> **How to preserve a chunk through re-ingest:** Edit the chunk's `content` directly in `chunks.jsonl` (or, in a future release, via a per-chunk markdown export) AND add `"_user_edited": true` to the chunk. On the next `/patchbay:ingest` run for that gear, the diff marks your edited chunk `! preserved` and never overwrites it. The flag persists across re-ingests until you remove it.

This is the load-bearing satisfier for INGEST-06 — user corrections survive re-ingest because the skill explicitly checks `_user_edited` before overwriting (Step 6 `! preserved` rule).

### Step 8: Closeout

After the write completes:

1. **Report low-confidence image categories** collected during Step 4. List them by chunk ID and prompt:

   > "[N] images had ambiguous categories — review and re-categorize manually if needed: [chunk-ids]"

2. **Suggest a git commit:**

   > `feat: ingest [Brand Item] manual ([N] chunks)`

3. **Offer the next ingest** if there are more gear items with manuals on disk:

   > "Want to ingest another manual? Remaining gear with manuals: [list]"

## Error handling

| Situation | Behavior |
|---|---|
| No gear folder for `<gear>` | Stop. Direct user to `patchbay:add-gear` or check folder naming. |
| `manuals/` missing or empty | Stop. Tell user to drop a PDF in `<gear_root>/<Brand Item>/manuals/`. |
| Multiple PDFs in `manuals/` | Present a numbered picker; accept a single index, multiple indices, or `all` (sequential, one-at-a-time). |
| Read tool fails on a batch | Retry once. If still failing, log the page range, skip that batch, continue. Surface skipped ranges at end-of-run. Do not abort the whole ingest. |
| Image does not fit any of the seven categories | Use closest match AND set `_low_confidence_category: true`. Collect for end-of-run review. Do not invent a new category. |
| Re-ingest: user picks `cancel` at the diff prompt | Leave `chunks.jsonl` untouched; `chunks.jsonl.bak` is NOT written. |
| `chunks.jsonl` is corrupt on re-ingest (un-parseable lines) | Refuse to overwrite. Offer to back up to `chunks.jsonl.corrupt.bak` and proceed as fresh ingest. |
| Scanned PDF with no embedded text (vision-only) | Proceed; flag the run with a warning that text-chunk content may be OCR-quality only. Recommend the user use the `_user_edited` flag to correct misreads. |

## UI layer notes

These decisions were made with a future interface in mind:

| Decision | UI implication |
|---|---|
| Append-only JSONL, one chunk per line | UI streams chunks page-by-page; no need to load the full file. Grep-friendly for in-app search. |
| Chunk-ID encodes page + sequence (`p016-c04`) | UI can render chunks in manual reading order without parsing `content`. |
| `provenance.rough_region` ∈ four values | UI highlights a quadrant of the source page on hover — no bounding box needed in v1. |
| `image_category` ∈ closed seven-value enum | UI renders category-specific affordances (`panel-diagram` → callout overlay; `marketing` → de-emphasize; `screen-screenshot` → state-aware tile). |
| `_user_edited: true` flag | UI shows a "you edited this" badge; prevents accidental overwrite via the UI's re-ingest button. |
| `_low_confidence_category: true` flag | UI shows a "needs review" badge; clicking it presents the seven categories as a picker. |
| Diff-on-reingest with explicit categories (`+ ~ ! = −`) | UI maps directly to a per-chunk diff list with checkboxes — same surface a CLI-level user sees. |
| `chunks.jsonl.bak` backup before re-ingest write | UI offers an "undo last ingest" button that restores from `.bak`. |
| Additive-fields contract (Phase 3/4 add types, never break) | UI built against Phase 2 schema continues to render Phase 3/4 chunks — unknown types render as opaque text; unknown fields ignored. No UI rebuild per phase. |

**The diff-on-reingest preservation flag (`_user_edited`) is the most load-bearing UI decision in this phase.** It is the contract between the user's manual corrections and the skill's automation. Both the CLI re-ingest path and any future UI re-ingest path key off this single field; both MUST honor it identically.
