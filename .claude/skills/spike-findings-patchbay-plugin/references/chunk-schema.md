# Chunk Schema (load-bearing — all sources serialize to this)

The unified schema that every Patchbay knowledge source produces. Validated across three independent source classes (PDF manual, YouTube video, web pages) in spikes 001 / 002c / 003. **All ingest skills must produce chunks in this shape; the downstream conversational AI relies on it for citation-hover and cross-source queries.**

## Requirements

These are non-negotiable design decisions from `.planning/spikes/MANIFEST.md`:

- **Provenance is mandatory per chunk.** Every chunk records source URL/file, location anchor, and `scraped_at` timestamp. Without this, the citation-hover UX cannot be built.
- **All images in a manual matter** — no filtering. Knob layouts, signal flow, charts, screenshots, marketing photos all become chunks.
- **The schema is one shape across all sources.** Manual chunks, YT chunks, and web chunks share the core fields. Source-specific fields are additive, not divergent.
- **Provenance schema `{source, location_anchor, scraped_at}` is sufficient for v1** — bounding boxes are a v2 concern.
- **Knowledge-graph chunk types belong in v1** — `artist_usage` and `cross_ref` are higher-leverage than flat content chunks.

## Core Schema

```json
{
  "id": "string — unique stable id, source-prefixed (e.g., 'eb-cb-clean-c01', 'p016-c04', 'yt-mm-002')",
  "type": "see chunk types table below",
  "source": "manual | youtube | equipboard | reddit | sweetwater | musicradar | ...",
  "tier_used": 0 | 1 | 2 | 3,
  "content": "string OR structured object — depends on type",
  "provenance": {
    "url": "string — for web sources",
    "manual": "string — filename for PDF sources",
    "page": "int — for PDF sources",
    "rough_region": "top | middle | bottom | full-page",
    "section": "string — DOM anchor or markdown heading",
    "deep_link": "string — URL with t=Xs or fragment",
    "timestamp_display": "string — '6:45–7:17' for YT",
    "scraped_at": "ISO date",
    "tier_label": "string — 'TIER_1_STATIC' | 'USER_PASTED' | 'TIER_2_BROWSER'"
  },
  "citation_targets": [
    { "type": "youtube | reddit-post | live-photo | article", "...": "type-specific fields" }
  ],
  "cross_source_match_candidates": ["array of gear/artist names also referenced in OTHER ingested sources"],
  "cross_source_match_note": "string explaining the corroboration"
}
```

Required: `id`, `type`, `source`, `content`, `provenance`. Everything else is additive.

## Chunk Types

| Type | Used by | Content shape | Why it matters |
|------|---------|---------------|----------------|
| `text` | manual, web | string (markdown) | Body copy, descriptions |
| `image` | manual, youtube | `{ image_category, description }` | Vision-described image. `image_category` ∈ marketing, signal-flow, panel-diagram, screen-screenshot, button-icon, icon, parameter-envelope |
| `transcript` | youtube | `{ start_time, end_time, text }` | Caption window |
| `multimodal_segment` | youtube | `{ timestamp, frame, frame_description, caption_text, what_audio_misses }` | Frame + aligned caption + analysis |
| `description` | web | string | Product/article description |
| `product_specs` | web (gear pages) | `{ brand, model, year, made_in, ... }` | Structured specs |
| `faq` | web (gear pages) | `[{ q, a }, ...]` | FAQ blocks |
| `artist_usage` | web (Equipboard) | `{ artist, artist_roles, associated_act, verification_type, verification_note, verbatim_quote, summary, alternatives_recommended }` | **The artist↔gear edge — highest-leverage type for the knowledge graph** |
| `cross_ref` | web (Equipboard) | `{ from_gear, relation, to_gear[], weight }` where relation ∈ used_with, similar_in_category | **Gear↔gear edges** |
| `genre_usage` | web (Equipboard) | `[{ genre, weight }, ...]` | Genre→gear weights (feeds user-taste-profile) |
| `review_section` | web (long-form Reddit, articles) | `{ section_header, key_thesis, summary, framing_takeaway, disclosures }` | Top-level review section |
| `review_subsection` | web (long-form) | `{ parameter, verdict }` | Sub-parameter within a review (e.g., "Noise floor: ultra low") |
| `comment_aggregate` | web (Reddit) | `[{ author, ups, snippet }, ...]` | Top comments digest |
| `external_resource` | any | `{ resource_type, title, site, url, updated, relevance }` | Tracks external citations — **foundation for citation-count → recommendation pattern** |

## Tiers (production fetch attempt level)

```
0 = manual user-paste (escape hatch when blocked)
1 = static fetch (curl/requests) — cheap default
2 = real browser (Claude_in_Chrome / Playwright stealth)
3 = visual capture + Claude vision ("screen reader")
```

`tier_used` field on each chunk records which tier produced it. Chunks from tier 2/3 can be flagged with lower freshness confidence (real-browser scrapes are slower → may be staler).

## How to Build It

1. **One TypeScript/Python type definition** for the schema, used by every ingest skill. Don't redefine per-source.
2. **Producers write append-only** to a per-gear store: `Gear/<Brand Item>/knowledge/chunks.jsonl` (or `.md` files with frontmatter — see "format decision" below).
3. **`citation_targets`** populated whenever a chunk references an external resource (a YouTube video, an article, a Reddit post). The downstream "citation count → recommendation" feature aggregates over this field.
4. **`cross_source_match_candidates`** populated when ingestion notices the chunk references a name (gear/artist) that another already-ingested source also references. Trivial implementation: load all chunk names into a set on first ingest, check against the set on second ingest.

## Format decision (still open)

Markdown-with-frontmatter (one file per chunk) vs JSONL (one record per line) was deferred from spike 002 (we used JSON for viewers, doesn't lock production).

**Recommendation when this becomes a phase decision:** JSONL for the storage format, markdown-with-frontmatter for the **export/share** format. JSONL is grep/jq friendly and append-only; markdown is human-readable. The two are mechanically convertible.

## What to Avoid

- **Don't filter images during manual ingest.** All images matter — even marketing photos. Spike 001 confirmed this on a real manual.
- **Don't summarize during ingest.** Producers preserve content verbatim with provenance; summarization is a downstream concern.
- **Don't bundle multiple distinct content blocks into one chunk** just because they're on the same page/timestamp. Citation-hover needs sentence/section-level granularity. Spike 001 split each manual page into 1-4 chunks; spike 003 split EB pages into 10+ chunks.
- **Don't put bounding boxes on the v1 critical path.** `rough_region` (top/middle/bottom) was sufficient for spike 001 verification; the user explicitly confirmed bounding boxes are a v2 concern.
- **Don't treat Whisper as required.** Spike 002 showed YouTube auto-captions + chapters/description are sufficient as the audio-text layer for v1; Whisper is a quality upgrade, not a v1 dependency.

## Constraints

- Claude Code's Read tool reads PDFs at up to **20 pages per call** — large manuals (>20 pages) require batching.
- Reddit `?.json` endpoint — no auth needed for public threads, returns ~400KB JSON for typical long-form review threads.
- Equipboard, Sweetwater, MusicRadar, etc. — protected by Cloudflare or similar; tier-1 static fetch returns 403. Document in `failures.log` and surface to user for tier-2 escalation.
- Vision tokens cost real money at production scale — sparse frame sampling (every 30s for YT video; every page for PDF) is the right default.

## Origin

Synthesized from spikes 001, 002a, 002c, 003.
Source files: `sources/001-vision-quality-pedal-manual/`, `sources/002a-yt-captions-only/`, `sources/002c-yt-multimodal-sampled/`, `sources/003-tiered-web-ingest/`
