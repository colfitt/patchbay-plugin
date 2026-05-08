---
name: spike-findings-patchbay-plugin
description: Implementation blueprint from spike experiments for Patchbay. Validated patterns, requirements, and verified knowledge for building patchbay:ingest, patchbay:research, and the underlying chunk schema. Auto-loaded during implementation work in this project.
---

<context>
## Project: patchbay-plugin

Patchbay is a Claude Code plugin for musicians — a project-agnostic toolkit that helps users use the gear they already own. The eventual UX is a conversational AI that answers gear questions and lets the user **hover any sentence in the answer to jump to the source** (manual page, video timestamp, review paragraph). That goal sets hard constraints on every upstream skill: knowledge is gear-anchored, chunked, and provenance-preserving.

This skill packages findings from four spike experiments that validated the architectural foundation before building the real `patchbay:ingest` and `patchbay:research` skills.

Spike sessions wrapped: 2026-05-07 / 2026-05-08
</context>

<requirements>
## Requirements

These are **non-negotiable design decisions** that emerged from user choices during spiking. Every implementation must honor them.

### Architecture

- Manual ingestion must preserve provenance per chunk (source type, page, location).
- All images in a manual matter — knob layouts, signal flow, charts, screenshots, marketing photos. **No filtering.**
- Output format must be reusable across source types — manual + YT + web all use the same chunk schema.
- Production path is a Claude Code skill — pipelines mirror what Claude already has (Read tool's PDF/image vision, etc.).
- Manual chunks must be expandable — external sources (YouTube tutorial transcripts, web articles, Reddit reviews) layer on top and cross-reference manual chunks.

### Chunk schema

- Provenance schema `{ source, location_anchor, scraped_at }` is sufficient for v1 — bounding boxes are a v2 concern.
- All chunk types share a common shape: `{ source, content/description, provenance }`. Source-specific fields are additive.
- Knowledge-graph chunk types belong in v1 — `artist_usage` (gear↔artist edge with verification source) and `cross_ref` (gear↔gear `used_with` / `similar_in_category` edges) are higher-leverage than flat content chunks.
- Cross-source corroboration is an emergent property — when multiple sources reference the same gear/artist/resource, citation count rises automatically and is queryable.

### Source priority order (locked)

1. **Manual** — backbone (validated spike 001)
2. **Equipboard / web articles / reviews** — primary external (validated spike 003)
3. **YouTube multimodal** — secondary reference for technique demos (validated spike 002c)
4. **YouTube captions-only** — fallback when video download is too expensive (spike 002a, partial)
5. **Reddit threads** — supplementary, especially long-form review threads (validated spike 003)

### YouTube ingestion

- Must be multimodal, not transcript-only — captions alone consistently lose information visible on screen.
- Cheaper baseline (002a) is a useful fallback layer, not a standalone product.

### Web scraping

- Cheap-by-default + user-driven escalation, NOT auto-fallback. Tier-1 static fetch tries first; on failure, write structured entry to `failures.log` with suggested escalation tier; user reviews and decides.
- Tiers: 1 = static fetch, 2 = Claude_in_Chrome browser automation, 3 = visual capture+vision, 0 = manual user-paste (escape hatch).
- `failures.log` is an append-only JSONL file with schema `{timestamp, url, tier_attempted, http_status, reason, reason_detail, suggested_escalation, last_attempted, retry_count}`.
- Reddit `?.json` suffix is the cheap path for that source class — no auth needed, full post + comments tree returned. Default to this for any reddit.com URL.
</requirements>

<findings_index>
## Feature Areas

| Area | Reference | Key Finding |
|------|-----------|-------------|
| Chunk schema (load-bearing) | [references/chunk-schema.md](references/chunk-schema.md) | Single schema across manual/YT/web. Knowledge-graph chunk types are the highest-leverage addition. |
| Manual ingestion | [references/manual-ingestion.md](references/manual-ingestion.md) | Claude's Read tool reads PDFs at up to 20 pages/call with native vision. Vision quality on dense diagrams (40 numbered callouts) is "pretty accurate" — sufficient for citation-hover RAG. |
| YouTube ingestion | [references/youtube-ingestion.md](references/youtube-ingestion.md) | Multimodal beats transcript-only. yt-dlp + ffmpeg + Claude vision at 30s frame intervals. YT is secondary, not primary. |
| Web scraping | [references/web-scraping.md](references/web-scraping.md) | Cheap-by-default + structured failure logging + user-driven escalation. Reddit `.json` cheap path. Equipboard is meta-aggregator (already includes YT review verbatim text). |
| Spike pattern (template) | [references/spike-pattern.md](references/spike-pattern.md) | Recurring template for future spikes — side-by-side viewer, inline chunks, two-column-no-responsive, dark theme with semantic badges. |

## Source Files

Original spike READMEs and core source files preserved in `sources/` for complete reference:

- `sources/001-vision-quality-pedal-manual/` — manual ingestion spike
- `sources/002a-yt-captions-only/` — captions-only YT spike (partial; includes production-ready `parse_vtt.py`)
- `sources/002c-yt-multimodal-sampled/` — multimodal YT spike
- `sources/003-tiered-web-ingest/` — web scraping spike (includes example `failures.log`)
</findings_index>

<metadata>
## Processed Spikes

- 001-vision-quality-pedal-manual (VALIDATED)
- 002a-yt-captions-only (PARTIAL)
- 002c-yt-multimodal-sampled (VALIDATED secondary)
- 003-tiered-web-ingest (VALIDATED)

Wrap-up date: 2026-05-08
</metadata>
