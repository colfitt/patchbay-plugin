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
- **All chunk types share a common schema** — `{ source, content/description, provenance }` works for manual pages, YT frames, and YT captions. Confirmed by spike 002c. Web-scraped chunks (next spike) will fit the same shape (added 2026-05-08 from spike 002 verification)
- **Source priority order for `patchbay:research`** — (1) manual = backbone, (2) web articles/reviews = primary external source (text+images, no alignment gap), (3) YouTube multimodal = secondary reference for technique demos, (4) YouTube captions-only = fallback when video download is too expensive (added 2026-05-08 from spike 002 verification)
- **YouTube ingestion must be multimodal, not transcript-only** — captions alone consistently lose information visible on screen (effect lists, parameter values, mode states). Cheaper baseline (002a) is a useful fallback layer, not a standalone product (added 2026-05-08 from spike 002 verification)
- **Web scraping uses cheap-by-default + user-driven escalation, not auto-fallback** — tier-1 static fetch tried first; on failure, write structured entry to `failures.log` with suggested escalation tier; user reviews and decides. Tiers: 1=static fetch, 2=Claude_in_Chrome browser automation, 3=visual capture+vision, 0=manual user-paste (escape hatch). Added 2026-05-08 from spike 003.
- **Knowledge-graph chunk types belong in the schema from v1** — `artist_usage` (gear↔artist edge with verification source) and `cross_ref` (gear↔gear `used_with` / `similar_in_category` edges) are higher-leverage than flat content chunks. Added 2026-05-08 from spike 003.
- **`failures.log` is an append-only JSONL file** — schema: `{timestamp, url, tier_attempted, http_status, reason, reason_detail, suggested_escalation, last_attempted, retry_count}`. Added 2026-05-08 from spike 003.
- **Reddit `.json` suffix is the cheap path for that source class** — no auth needed, full post + comments tree returned. Production should default to this for any reddit.com URL before attempting other tiers. Added 2026-05-08 from spike 003.
- **Cross-source corroboration is an emergent property of the schema** — when multiple independent sources reference the same gear/artist/resource, citation count rises automatically and is queryable. Spike 003 surfaced 3 cross-source gear matches without explicit design effort. Added 2026-05-08 from spike 003.
- **Tier 2 (Claude_in_Chrome) AND tier 3 (computer-use) are both first-class escalation paths** — they have different failure modes (tier 2: extension automation can be detected; tier 3: bulletproof against anti-bot but slower and requires per-session permission). Production should support both and let the user choose. `failures.log` `suggested_escalation` field expands to `2 | 3 | "either" | "manual-paste" | "skip"`. Added 2026-05-08 from spike 003c.
- **Production tier-2 escalation must precheck `Claude_in_Chrome` extension connection** — `list_connected_browsers` returning `[]` is a setup prerequisite, not a runtime failure. Surface install instructions, don't fail silently. Added 2026-05-08 from spike 003c.
- **Tier-3 captures content lower tiers miss, even when those lower tiers work** — visual capture reads text embedded in images (knob labels on product photos, screen states in screenshots) that DOM-text scraping cannot. Same architectural pattern as spike 002c (frames vs transcript). Added 2026-05-08 from spike 003c.

## Spikes

| # | Name | Type | Validates | Verdict | Tags |
|---|------|------|-----------|---------|------|
| 001 | vision-quality-pedal-manual | standard | Read tool's vision quality on a real gear manual is useful enough for citation-hover RAG | ✓ VALIDATED | ingest, vision, quality |
| 002a | yt-captions-only | comparison | YouTube auto-captions + metadata alone produce useful chunks (cheapest baseline) | ⚠ PARTIAL | research, youtube, transcript, baseline |
| 002c | yt-multimodal-sampled | comparison | Captions + sampled frames + per-frame visual analysis closes the gap that transcript-only ingest leaves open | ✓ VALIDATED (secondary) | research, youtube, transcript, multimodal, frames, vision |
| 003 | tiered-web-ingest | standard | Cheap-by-default web scraping with structured failure logging — tier-1 static fetch + tier-2 escalation as user-driven choice; new chunk types (artist_usage, cross_ref) extend schema into knowledge-graph territory | ✓ VALIDATED | research, web-scrape, equipboard, reddit, cloudflare, knowledge-graph |
| 003b | tier2-claude-in-chrome-escalation | comparison | Real browser via Claude_in_Chrome MCP can ingest a Cloudflare-blocked URL when extension is connected | OPEN (prereq: user installs extension) | research, web-scrape, tier-2, claude-in-chrome |
| 003c | tier3-computer-use-escalation | comparison | computer-use MCP + Chrome read-tier + Claude vision can ingest a Cloudflare-blocked URL with no extension install — and captures content (image labels) that lower tiers miss | ✓ VALIDATED | research, web-scrape, tier-3, computer-use, vision, escalation |
