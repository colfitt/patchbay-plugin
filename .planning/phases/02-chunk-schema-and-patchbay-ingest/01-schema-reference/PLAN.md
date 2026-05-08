# Phase 2 — Plan 01: Schema reference doc

**Phase:** 2 (Chunk schema + patchbay:ingest)
**Plan:** 01 of 03
**Wave:** 1
**Depends on:** none (first plan)
**Autonomous:** yes

---

## Goal

Produce the load-bearing schema reference that the `patchbay-ingest` skill (and Phases 3 / 4 skills) will all cite as the source of truth for chunk shape. After this plan, every implementer downstream has a single file to read for "what does a chunk look like" and "what counts as a valid image_category."

**Observable outcome:** `skills/patchbay-ingest/references/chunk-schema.md` exists, parses as valid markdown, contains a complete chunk-shape table, the seven-value image-category enum, the chunk-id format spec, and an explicit "additive fields" contract for Phase 3 / 4 chunk types.

---

## Files to create

- `skills/patchbay-ingest/references/chunk-schema.md` (new)
- `skills/patchbay-ingest/references/image-categories.md` (new — focused enum reference, kept separate so SKILL.md can link directly)

> **Skill name decision:** `patchbay-ingest` (hyphenated, matches existing `liner-notes` and `dialed-in` convention in `skills/`). Slash command surface is `/patchbay:ingest <gear>` per ROADMAP § Phase 2.

## Files NOT to create

- Do not create `skills/patchbay-ingest/SKILL.md` here — that is Plan 02's deliverable. This plan produces references only.
- Do not create `skills/ingest/` — that name conflicts with the slash command form and breaks the established `skills/<noun-phrase>/` pattern.

## Files NOT to modify

- `.claude/skills/spike-findings-patchbay-plugin/references/chunk-schema.md` — that is the spike-findings reference (input). This plan produces a *production* schema reference under `skills/patchbay-ingest/references/`. Adapt freely; do not edit the spike-findings copy.

---

## Concrete steps

### Step 1: Read the source schema

Read end-to-end:
- `.claude/skills/spike-findings-patchbay-plugin/references/chunk-schema.md` (canonical source)
- `.claude/skills/spike-findings-patchbay-plugin/references/manual-ingestion.md` (for the seven image-category descriptions and examples)
- `.planning/REQUIREMENTS.md` § CHUNK-01..05 (the requirements the schema doc must satisfy)

### Step 2: Write `skills/patchbay-ingest/references/chunk-schema.md`

Required sections, in order:

1. **Title + one-paragraph purpose** — "The shape every chunk in `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` conforms to. Manual / web / YouTube ingest all serialize to this shape."
2. **Required fields table** — `id`, `type`, `source`, `content`, `provenance` (sub-fields: `manual`, `page`, `rough_region`, `scraped_at`). Match the spike-findings shape; CHUNK-02 / criterion 2 is satisfied here.
3. **Optional / additive fields table** — `tier_used`, `citation_targets`, `cross_source_match_candidates`, `cross_source_match_note`, source-specific blocks (`image_category`, `start_time`, `artist`, `from_gear`, etc.). Each row says which chunk type uses it.
4. **Chunk types table** — copy/adapt the table from spike-findings: `text`, `image`, `transcript`, `multimodal_segment`, `description`, `product_specs`, `faq`, `artist_usage`, `cross_ref`, `genre_usage`, `review_section`, `review_subsection`, `comment_aggregate`, `external_resource`. For each: which source produces it, content shape, why it matters. Phase 2 only writes `text` and `image`; the rest are documented up front so Phase 3 / 4 don't need a schema migration.
5. **Chunk ID format spec** — `<source-prefix>-<location>-c<NN>` where:
   - manual: `p016-c04` (p = page, c = chunk-within-page, zero-padded, sequential per page)
   - web: `eb-cb-clean-c01` (source-prefix + slug + counter)
   - youtube: `yt-mm-002` (source-prefix + counter)
   - IDs are stable across re-ingest unless the chunk's *content block* changes (page/region/sequence preserved → ID preserved).
6. **Additive fields contract (CHUNK-04, criterion 6)** — explicit one-paragraph guarantee: *Phase 3 and Phase 4 add new chunk `type` values (`artist_usage`, `cross_ref`, `external_resource`, etc.) and new optional fields (`tier_used`, `citation_targets`, etc.). They do NOT modify required fields, do NOT remove existing types, and do NOT change the meaning of any field defined in this document. A reader written for the Phase 2 schema will continue to parse Phase 3 / 4 chunks (unknown fields ignored, unknown `type` values surface as opaque-content text-only chunks).*
7. **What goes in `chunks.jsonl`** — one JSON object per line, append-only, UTF-8, no trailing comma, newline-terminated. Grep / jq friendly. Reference CHUNK-03.
8. **Validation rules** — concrete checks any reader can run:
   - required fields present
   - `provenance.scraped_at` parses as ISO date
   - `id` is unique within the file
   - if `type == "image"`, `content.image_category` ∈ the seven-value enum (link to `image-categories.md`)
9. **What NOT to do** — verbatim or paraphrased from spike-findings: don't filter images, don't summarize during ingest, don't bundle multiple content blocks into one chunk, don't put bounding boxes in v1.

**Voice / style:** match spike-findings reference docs (declarative, terse, requirement-cited). No marketing prose.

### Step 3: Write `skills/patchbay-ingest/references/image-categories.md`

Focused enum reference. Required content:

1. The seven categories as a table: `marketing`, `signal-flow`, `panel-diagram`, `screen-screenshot`, `button-icon`, `icon`, `parameter-envelope`. For each: one-line definition, an example from a real manual, and a "describe how" rule (e.g., panel-diagram: "describe every numbered callout — text is on-image and won't be in surrounding paragraphs").
2. **Edge-case rule (mandatory):** "If a manual image does not cleanly fit any category, prefer the closest match from the existing seven; do not invent a new category. Surface the misfit to the user via a `_low_confidence_category: true` field on the chunk and request review at end of ingest. Adding an eighth category is a v2 spike, not an in-flight skill decision." This satisfies the "image-category validation" anti-shallow rule.
3. **Cross-link** — at the bottom, "See `chunk-schema.md` § Chunk types for how `image_category` slots into the `image` chunk's content shape."

### Step 4: Self-check against requirements

Before finishing, walk the requirements in `.planning/REQUIREMENTS.md` § CHUNK and verify each has a locus in the docs you wrote:

- CHUNK-01 (unified schema across sources) → § Required fields + § Chunk types
- CHUNK-02 (provenance fields per chunk) → § Required fields → `provenance` sub-fields
- CHUNK-03 (per-gear knowledge store at `knowledge/chunks.jsonl`, append-only) → § What goes in `chunks.jsonl`
- CHUNK-04 (knowledge-graph chunk types: `artist_usage`, `cross_ref`) → § Chunk types
- CHUNK-05 (`external_resource` chunks) → § Chunk types
- Criterion 6 (additive-fields, no schema break for Phase 3 / 4) → § Additive fields contract

If any requirement has no clear locus, add it before declaring done.

---

## Verification

Plan succeeds when **all** of these are true:

1. `skills/patchbay-ingest/references/chunk-schema.md` exists.
2. `skills/patchbay-ingest/references/image-categories.md` exists.
3. Both files parse as well-formed markdown (no broken tables, no orphaned headings).
4. `chunk-schema.md` contains all nine required sections from Step 2 (title + 8 numbered sections).
5. `image-categories.md` contains the seven-value enum, edge-case rule, and cross-link to `chunk-schema.md`.
6. The five CHUNK requirements + criterion 6 each have a clear locus (verifiable by grep — e.g., `grep -i "additive" chunk-schema.md` returns the contract paragraph).
7. The seven `image_category` values are spelled exactly: `marketing`, `signal-flow`, `panel-diagram`, `screen-screenshot`, `button-icon`, `icon`, `parameter-envelope`. (Hyphens, lowercase. UI rendering will key off these strings.)

**Manual sanity check** (one minute): open both files in a markdown viewer, confirm tables render and headings nest correctly.

---

## Requirements covered

- **CHUNK-01** — Unified chunk schema across manual / YT / web sources
- **CHUNK-02** — Provenance fields per chunk
- **CHUNK-03** — Per-gear knowledge store at `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` (append-only JSONL)
- **CHUNK-04** — Knowledge-graph chunk types: `artist_usage`, `cross_ref`
- **CHUNK-05** — `external_resource` chunks for citation tracking

(INGEST-01..06 are addressed by Plan 02. Phase 2 success criterion 6 — additive fields, no schema break — is anchored in this plan's § Additive fields contract.)

---

## UI layer notes

Per the always-include-UI-notes feedback rule, decisions in this plan that shape future UI:

| Decision | UI implication |
|---|---|
| Required fields stable across sources | UI can build one citation-hover component, not per-source variants |
| `provenance.rough_region` ∈ `top \| middle \| bottom \| full-page` | UI can highlight a quadrant of a manual page when user hovers a chunk — no bounding box needed for v1 |
| Chunk-id format encodes location (`p016-c04`) | UI can sort/group chunks by manual page in render order without parsing content |
| `image_category` is a closed enum of seven | UI can render category-specific affordances (panel-diagram → callout overlay; screen-screenshot → state-aware highlight; marketing → de-emphasize) |
| `_low_confidence_category` flag on misfit images | UI surfaces a "needs review" badge on those chunks |
| Append-only JSONL, one chunk per line | UI can stream/page chunks without loading full file; grep-friendly for in-app search |
| Additive-fields contract | UI built against Phase 2 schema continues to render Phase 3 / 4 chunks (unknown fields ignored, unknown types render as text-only) — no UI rebuild per phase |

---

## Out of scope for Plan 01

- The skill body itself (Plan 02)
- Diff-on-reingest behaviour spec (Plan 02 — uses the schema, doesn't define it)
- End-to-end verification against a real manual (Plan 03)
- Editing the spike-findings reference doc (it stays the input artifact; production lives under `skills/`)
