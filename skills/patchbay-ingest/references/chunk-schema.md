# Chunk Schema (load-bearing — every source serializes to this)

The shape every chunk in `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` conforms to. Manual / web / YouTube ingest all serialize to this shape, so a single reader can render any chunk and the downstream conversational AI can do citation-hover and cross-source queries without per-source branching.

Validated across three independent source classes (PDF manual, YouTube video, web pages) in spikes 001 / 002c / 003. **All ingest skills must produce chunks in this shape.**

## Required fields

Every chunk — regardless of source — has these five fields. A reader can refuse any chunk missing any of them.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique stable id, source-prefixed. Stable across re-ingest unless the underlying content block moves. See § Chunk ID format. |
| `type` | string | One of the values in § Chunk types. Drives how `content` is interpreted. |
| `source` | string | Top-level source class: `manual` \| `youtube` \| `equipboard` \| `reddit` \| `sweetwater` \| `musicradar` \| … (open enum — additive). |
| `content` | string OR object | Per-`type` content shape. `text` chunks are strings; structured types are objects. |
| `provenance` | object | The citation-hover substrate. See sub-fields below. |

### `provenance` sub-fields

The citation-hover UX downstream cannot be built without these. Manual chunks always carry `manual`, `page`, `rough_region`, `scraped_at`; other sources fill the source-appropriate subset.

| Sub-field | Type | Required for | Description |
|---|---|---|---|
| `manual` | string | manual | Filename of the source PDF (e.g., `MPC Sample - User Guide - v1.3.pdf`). |
| `page` | int | manual | 1-indexed page number in the PDF. |
| `rough_region` | string | manual, web | `top` \| `middle` \| `bottom` \| `full-page`. v1 substitute for bounding boxes. |
| `scraped_at` | string (ISO date) | all | ISO 8601 timestamp set once at the start of the ingest run. |
| `url` | string | web, youtube | Source URL. |
| `section` | string | web | DOM anchor or markdown heading the chunk came from. |
| `deep_link` | string | web, youtube | URL with `?t=Xs` fragment (YT) or `#anchor` (web). |
| `timestamp_display` | string | youtube | Human-readable timestamp range (e.g., `6:45–7:17`). |

`provenance.scraped_at` is mandatory on every chunk. Other sub-fields are required per source class.

## Optional / additive fields

These fields are present on some chunks, absent on others. A reader written for the required-field set above MUST tolerate (ignore) any additive field it does not recognize. This is the contract that lets Phase 3 / 4 add fields without a schema migration.

| Field | Type | Used by | Description |
|---|---|---|---|
| `tier_used` | int (0–3) | web | Which fetch tier produced the chunk. 0 = manual user-paste, 1 = static, 2 = real browser, 3 = visual capture. Lets the UI surface freshness confidence. |
| `citation_targets` | array of object | any | External resources referenced by this chunk (`{type, url, …}`). Phase 4 aggregates over this to power the citation-count recommendation. |
| `cross_source_match_candidates` | array of string | any | Names (gear / artist / external resource) that another already-ingested chunk also references. Populated automatically during Phase 3 ingestion. |
| `cross_source_match_note` | string | any | One-line explanation of the corroboration. |
| `_user_edited` | boolean | any | Set by the user to mark a chunk as manually corrected. `patchbay-ingest` MUST NOT overwrite chunks where this is `true` on re-ingest. See § What goes in `chunks.jsonl`. |
| `_low_confidence_category` | boolean | image chunks | Set during ingest when an image does not cleanly fit any of the seven `image_category` values. Surfaces a "needs review" badge in the UI. |

Source-specific content shapes (e.g., `image_category` inside an image chunk's `content` object, or `artist_roles` inside an `artist_usage` chunk's `content` object) are documented in § Chunk types below.

## Chunk types

Phase 2 ingest writes `text` and `image` chunks only. Every other type listed here is reserved for Phase 3 / 4 and is documented up front so the schema does not need a migration when those phases land.

| Type | Used by | Content shape | Why it matters |
|---|---|---|---|
| `text` | manual, web | string (markdown) | Body copy, section bodies, descriptions. Phase 2 writes this. |
| `image` | manual, youtube | `{ image_category, description }` | Vision-described image. `image_category` ∈ the seven-value enum in [image-categories.md](./image-categories.md). Phase 2 writes this. |
| `transcript` | youtube | `{ start_time, end_time, text }` | One caption window. |
| `multimodal_segment` | youtube | `{ timestamp, frame, frame_description, caption_text, what_audio_misses }` | A sampled video frame + its aligned caption + a delta of what the audio alone misses. |
| `description` | web | string | Product or article description. |
| `product_specs` | web (gear pages) | `{ brand, model, year, made_in, … }` | Structured specs lifted from an Equipboard or manufacturer page. |
| `faq` | web (gear pages) | `[{ q, a }, …]` | FAQ blocks. |
| `artist_usage` | web (Equipboard) | `{ artist, artist_roles, associated_act, verification_type, verification_note, verbatim_quote, summary, alternatives_recommended }` | **The artist↔gear edge — highest-leverage type for the knowledge graph.** |
| `cross_ref` | web (Equipboard) | `{ from_gear, relation, to_gear[], weight }` where `relation` ∈ `used_with` \| `similar_in_category` | **Gear↔gear edges.** |
| `genre_usage` | web (Equipboard) | `[{ genre, weight }, …]` | Genre→gear weights (feeds the future user-taste-profile feature). |
| `review_section` | web (long-form Reddit, articles) | `{ section_header, key_thesis, summary, framing_takeaway, disclosures }` | A top-level section of a long-form review. |
| `review_subsection` | web (long-form) | `{ parameter, verdict }` | A sub-parameter within a review (e.g., "Noise floor: ultra low"). |
| `comment_aggregate` | web (Reddit) | `[{ author, ups, snippet }, …]` | Top-comments digest for a thread. |
| `external_resource` | any | `{ resource_type, creator, title, url, updated, relevance, citing_chunk_ids[] }` | Tracks an external citation. **Foundation for the Phase 4 citation-count recommendation pattern.** |

Phase 2 readers that encounter a chunk with a `type` they do not recognize MUST treat it as opaque (render only `content` as text if `content` is a string; skip rendering otherwise) — they MUST NOT error out. This is the read-side half of the additive-fields contract.

## Chunk ID format

`<source-prefix>-<location>-c<NN>` where `c<NN>` is a zero-padded counter scoped to the location.

| Source | Format | Example | Notes |
|---|---|---|---|
| manual | `p<NNN>-c<NN>` | `p016-c04` | `p` = page number (zero-padded to 3 digits), `c` = chunk-within-page (zero-padded to 2 digits, sequential top-to-bottom). |
| web | `<source-prefix>-<slug>-c<NN>` | `eb-cb-clean-c01` | `eb` = Equipboard, `cb-clean` = page slug, `c` = counter. |
| youtube | `yt-<short-tag>-<NNN>` | `yt-mm-002` | `yt` + short identifier (e.g., `mm` for "multimodal") + counter. |

**Stability rule:** an ID is stable across re-ingest as long as the underlying content block (manual page + region + sequence, web page + DOM anchor, video segment) does not move. If the model produces a different *description* for the same image on page 16, the ID stays `p016-c04` — the diff machinery in `patchbay-ingest` uses the ID as the join key. If the underlying content actually shifts (the manual gets re-typeset and page 16 becomes page 17), the IDs change and the old chunks appear as `- removed` in the diff.

## Additive fields contract

Phase 3 and Phase 4 add new chunk `type` values (`artist_usage`, `cross_ref`, `external_resource`, etc.) and new optional fields (`tier_used`, `citation_targets`, `cross_source_match_candidates`, etc.). They do NOT modify required fields, do NOT remove existing types, and do NOT change the meaning of any field defined in this document. **A reader written for the Phase 2 schema continues to parse Phase 3 / 4 chunks** — unknown fields are ignored, unknown `type` values render as opaque-content text-only chunks (or are skipped).

This guarantee is what lets Phase 2 ship a usable artifact today without blocking on Phase 3 / 4 design. Both later phases will append to the same `chunks.jsonl` file; both will write chunks the Phase 2 reader can either render or safely ignore.

## What goes in `chunks.jsonl`

The per-gear knowledge store: `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` (CHUNK-03).

- **One JSON object per line.** No pretty-printing across lines, no `[` / `]` wrapping array, no trailing comma.
- **UTF-8 encoded.**
- **Append-only at the line level.** Writers (Phase 2 ingest, Phase 3 research) append chunks; they never rewrite earlier lines except during a re-ingest diff confirmed by the user.
- **Newline-terminated.** The file ends with `\n` so `wc -l` matches chunk count and `tail -1` reads cleanly.
- **Grep- and jq-friendly.** A user can run `grep '"type":"image"'` or `jq 'select(.provenance.page == 16)'` against the file directly.

Multi-source contributions accumulate into the same file: manual ingest writes `manual` chunks, `patchbay-research` later appends `equipboard` / `reddit` / `youtube` chunks. The IDs do not collide because each source uses a distinct prefix (`p016-c04` vs `eb-…` vs `yt-…`).

### User edits

A user can edit a chunk's `content` directly in `chunks.jsonl` (or via a per-chunk markdown export, planned for v2.x). To mark the edit as permanent, the user adds `"_user_edited": true` to the chunk. `patchbay-ingest` MUST NOT overwrite chunks where this flag is `true` on re-ingest; it surfaces them in the diff as `! preserved`. This is the load-bearing satisfier for INGEST-06.

## Validation rules

A reader (or test harness) can apply these checks line-by-line:

1. **JSON-parseable.** Every line parses as a JSON object.
2. **Required fields present.** Every chunk has `id`, `type`, `source`, `content`, `provenance`.
3. **`provenance.scraped_at` parses as ISO 8601.**
4. **`id` is unique within the file.** A duplicate ID is a producer bug.
5. **Image chunks have a valid `image_category`.** If `type == "image"`, `content.image_category` MUST be one of the seven values in [image-categories.md](./image-categories.md). `_low_confidence_category: true` is allowed alongside a closest-match category; an invented category is not.
6. **Manual chunks have `provenance.manual` and `provenance.page`.** Web chunks have `provenance.url`. YouTube chunks have `provenance.url` and `provenance.timestamp_display`.

A `chunks.jsonl` that fails any of these checks is malformed; `patchbay-ingest` on re-ingest treats it as corrupt and offers to back up to `chunks.jsonl.corrupt.bak` before proceeding.

## What NOT to do

- **Don't filter images during ingest.** All images matter — marketing covers, signal-flow diagrams, panel-photos, screenshots, parameter charts. Spike 001 confirmed this on a real manual; the user explicitly endorsed it. The seven `image_category` values are inclusive by design.
- **Don't summarize during ingest.** Producers preserve content verbatim (text → markdown of the page; images → literal vision description including every numbered callout). Summarization is a downstream concern handled by the conversational AI.
- **Don't bundle multiple content blocks into one chunk** just because they share a page or timestamp. Citation-hover needs section-level granularity. Spike 001 split each manual page into 1–4 chunks; spike 003 split Equipboard pages into 10+ chunks.
- **Don't put bounding boxes in v1.** `provenance.rough_region` (top / middle / bottom / full-page) was sufficient for spike 001 verification; bounding boxes are a v2 spike, not an in-flight skill decision.
- **Don't redefine the schema per source.** A new source class (e.g., GearSpace forums in v3) adds new chunk `type` values or new content-shape sub-fields — it does not invent a parallel chunk envelope. The required-field set is locked.
- **Don't write `chunks.jsonl` from anywhere but the production ingest skills.** Hand-authored chunks are fine for testing but should not be committed to a user's gear folder without going through `patchbay-ingest`'s ID-generation and validation path.

## Origin

Synthesized from spikes 001 (manual), 002c (YouTube multimodal), 003 (web tiered fetch). The canonical input is `.claude/skills/spike-findings-patchbay-plugin/references/chunk-schema.md`; this document is the production reference, adapted from that input to anchor the schema in the user's repo at the location production skills cite.
