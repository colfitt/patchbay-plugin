# Phase 2 — Plan 01: SUMMARY

**Status:** Complete
**Verdict:** All verification criteria met.

## What was built

Two production-location reference docs that anchor the chunk schema for the entire v2.0 milestone:

- [skills/patchbay-ingest/references/chunk-schema.md](../../../../skills/patchbay-ingest/references/chunk-schema.md) — the load-bearing schema doc. Required fields table + optional/additive fields table + 14-row chunk types table + chunk-ID format spec + explicit additive-fields contract + `chunks.jsonl` format rules + validation rules + what-not-to-do.
- [skills/patchbay-ingest/references/image-categories.md](../../../../skills/patchbay-ingest/references/image-categories.md) — focused enum reference. Seven values spelled exactly, per-category definitions with manual examples and "how to describe it" rules, edge-case rule mandating closest-match + `_low_confidence_category: true` instead of inventing categories.

## Key decisions (locked in this plan, downstream cites)

| Decision | Locus | Rationale |
|---|---|---|
| Required field set is `id`, `type`, `source`, `content`, `provenance` (5 fields) | chunk-schema § Required fields | Every chunk validates against this minimum; missing any is malformed. Source-specific richness lives in `provenance` sub-fields and `content` shape. |
| `provenance` sub-fields are per-source (`manual`/`page` for PDF, `url`/`section` for web, `url`/`timestamp_display` for YT) but `scraped_at` is mandatory on every chunk | chunk-schema § provenance sub-fields | Citation-hover UX needs a per-source deep-link; freshness needs a universal timestamp. |
| Chunk-ID format encodes location (`p016-c04` for page 16 chunk 4) so IDs are stable across re-ingest | chunk-schema § Chunk ID format | Diff machinery in Plan 02 uses ID as the join key. |
| Phase 2 writes `text` and `image` only; the other 12 types are documented now to lock the additive-fields contract | chunk-schema § Chunk types | Phase 3/4 append to the same `chunks.jsonl` without a schema migration. |
| Image-category enum is closed at seven values; misfit images use closest-match + `_low_confidence_category: true` | image-categories § Edge-case rule | An eighth category is a v2 spike, not an in-flight decision. |
| Readers MUST tolerate unknown `type` values and unknown additive fields (treat as opaque content or skip) | chunk-schema § Additive fields contract | Half of the schema-stability contract. Without read-side tolerance, write-side additivity doesn't help. |

## Verification (self-check against Plan 01 § Verification)

- [x] `skills/patchbay-ingest/references/chunk-schema.md` exists.
- [x] `skills/patchbay-ingest/references/image-categories.md` exists.
- [x] Both files parse as well-formed markdown (tables render, headings nest).
- [x] `chunk-schema.md` contains all nine required sections from Plan 01 Step 2: title + Required fields + Optional/additive fields + Chunk types + Chunk ID format + Additive fields contract + What goes in chunks.jsonl + Validation rules + What NOT to do.
- [x] `image-categories.md` contains the seven-value enum, edge-case rule, and cross-link to `chunk-schema.md`.
- [x] CHUNK-01..05 + criterion 6 each have a clear locus (grep verifies; `additive` appears 5x in chunk-schema.md).
- [x] Seven `image_category` values spelled exactly: `marketing`, `signal-flow`, `panel-diagram`, `screen-screenshot`, `button-icon`, `icon`, `parameter-envelope`.

## Requirements covered

- **CHUNK-01** — Unified chunk schema across manual / YT / web sources → § Required fields + § Chunk types
- **CHUNK-02** — Provenance fields per chunk → § provenance sub-fields
- **CHUNK-03** — Per-gear knowledge store at `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` (append-only JSONL) → § What goes in `chunks.jsonl`
- **CHUNK-04** — Knowledge-graph chunk types (`artist_usage`, `cross_ref`) → § Chunk types (rows present)
- **CHUNK-05** — `external_resource` chunks → § Chunk types (row present)
- **Phase 2 success criterion 6** — Additive fields, no schema break for Phase 3/4 → § Additive fields contract

## Key files created

- `skills/patchbay-ingest/references/chunk-schema.md`
- `skills/patchbay-ingest/references/image-categories.md`

## Deviations from plan

None. The plan was followed step-by-step. The spike-findings input doc was used as canonical source per Plan 01 Step 1 and was NOT modified per Plan 01 § Files NOT to modify.

## Hand-off to Plan 02

Plan 02 (skill body) cites both reference files in its "Before starting" pointer block. The image-category enum (closed, seven values) and the chunk-ID format (`p<NNN>-c<NN>` for manual) are the load-bearing inputs Plan 02 needs.
