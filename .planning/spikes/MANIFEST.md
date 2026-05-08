# Spike Manifest

## Idea

Validate the technical foundation for `patchbay:ingest` and `patchbay:research` — the gear-anchored, citation-traceable knowledge architecture described in [.planning/notes/knowledge-architecture.md](../notes/knowledge-architecture.md).

The eventual UX is a conversational AI that answers gear questions and lets the user hover any sentence to jump to the source — exact manual page, video timestamp, or review paragraph. That goal sets hard constraints on every upstream skill: knowledge must be chunked, gear-anchored, and provenance-preserving.

These spikes prove the manual-ingestion half is feasible.

## Requirements

(Tracked as they emerge from spike findings and user choices)

- Manual ingestion must preserve provenance per chunk (source type, page, location)
- All images in a manual matter — knob layouts, signal flow, charts, screenshots, marketing photos. No filtering.
- Output format must be reusable by `patchbay:research` (web sources)
- Production path is a Claude Code skill — the spike technique should mirror production
- **Manual chunks must be expandable** — external sources (especially YouTube tutorial transcripts) should layer on top and cross-reference manual chunks (added 2026-05-07 from spike 001 verification)
- Provenance schema `{ manual, page, rough_region }` is sufficient for v1 — bounding boxes are a v2 concern (added 2026-05-07 from spike 001 verification)

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | vision-quality-pedal-manual | standard | Read tool's vision quality on a real gear manual is useful enough for citation-hover RAG | ✓ VALIDATED | ingest, vision, quality |
