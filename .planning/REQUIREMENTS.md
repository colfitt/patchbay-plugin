# Requirements — Milestone v2.0 (gear-knowledge)

The chunk schema and ingest pipelines were validated across 6 spikes (001 / 002a / 002c / 003 / 003b / 003c). This document scopes the v2.0 requirements that turn those spike findings into shipped skills.

Each REQ-ID maps to exactly one phase. Coverage is verified during roadmap creation.

> **Previous milestone (v1.0 / dialed-in)** shipped Phase 1 successfully — see git log for the validated requirements (SKILL-01..03, PROC-01..08, DATA-01..03, ERR-01..02, UI-01..02). They have been moved into PROJECT.md `Requirements › Validated`.

## v2.0 Requirements

### CHUNK — Chunk schema + per-gear knowledge store

The load-bearing data layer all v2.0 skills serialize to.

- [ ] **CHUNK-01**: User has one unified chunk schema across manual / YouTube / web sources, matching the shape validated in [spike-findings/chunk-schema.md](../.claude/skills/spike-findings-patchbay-plugin/references/chunk-schema.md). Source-specific fields are additive, never divergent.
- [ ] **CHUNK-02**: Every chunk carries provenance fields (`source`, `location_anchor`, `scraped_at`, source-specific deep_link / page / timestamp_display). Citation-hover UX cannot be built without this.
- [ ] **CHUNK-03**: User has a per-gear knowledge store at `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` — append-only JSONL, one chunk per line, grep-friendly.
- [ ] **CHUNK-04**: User has knowledge-graph chunk types: `artist_usage` (gear↔artist edges with verification source) and `cross_ref` (gear↔gear `used_with` / `similar_in_category` edges with weights).
- [ ] **CHUNK-05**: User has `external_resource` chunks tracking external URLs (YouTube videos with creator + title, articles with domain + headline) — the data substrate for the citation-count recommendation feature.

### INGEST — `patchbay:ingest` skill

Manual PDF → chunks. Backbone of the gear knowledge graph.

- [ ] **INGEST-01**: User can run `/patchbay:ingest <gear>` against `<gear_root>/<Brand Item>/manuals/*.pdf` and get a populated `chunks.jsonl` for that gear.
- [ ] **INGEST-02**: All images in the manual are described — no filtering. Each image chunk has `image_category` ∈ marketing / signal-flow / panel-diagram / screen-screenshot / button-icon / icon / parameter-envelope.
- [ ] **INGEST-03**: Multi-page PDFs are handled via Read tool batching (20 pages per call); chunks assemble correctly with no gaps.
- [ ] **INGEST-04**: Each manual page produces 1-4 chunks split by content type and logical block (text section vs image vs control close-up). Sentence/section-level granularity, not per-page.
- [ ] **INGEST-05**: Re-running ingest on a manual that already has chunks produces a diff and asks the user to confirm before overwriting — preserves any chunks the user has corrected.
- [ ] **INGEST-06**: User can edit chunks directly in `chunks.jsonl` (or a per-chunk markdown export) and the corrections survive re-ingest.

### RESEARCH — `patchbay:research` skill

Multi-source web ingest with tiered fetch + user-driven escalation.

- [x] **RESEARCH-01**: User can run `/patchbay:research <gear>` and get web sources ingested into the gear's `chunks.jsonl`.
- [x] **RESEARCH-02**: Tier-1 static fetch (`requests` + `BeautifulSoup`) is tried first for every URL. On HTTP non-2xx or detected anti-bot challenge, the failure is logged.
- [x] **RESEARCH-03**: `failures.log` is append-only JSONL with schema `{timestamp, url, tier_attempted, http_status, reason, reason_detail, suggested_escalation, last_attempted, retry_count}`. `reason` ∈ cloudflare-block / bot-detected / js-required / rate-limited / paywall / 404 / timeout / other. `suggested_escalation` ∈ `2 | 3 | "either" | "manual-paste" | "skip"`.
- [ ] **RESEARCH-04**: User can review `failures.log` via a sub-command (`/patchbay:research --review-failures`) and choose, per entry, to escalate to tier 2, tier 3, paste manually, or skip. **No auto-fallback** between tiers.
- [ ] **RESEARCH-05**: Tier-2 escalation prechecks `mcp__Claude_in_Chrome__list_connected_browsers`; if empty, surfaces extension install instructions instead of failing silently.
- [x] **RESEARCH-06**: Reddit URLs (`reddit.com/r/.../comments/...`) automatically use the `?.json` suffix path at tier 1 — no escalation required for that source class.
- [ ] **RESEARCH-07**: YouTube URLs are ingested multimodally (yt-dlp captions + `parse_vtt.py` + ffmpeg frame sampling at 30s + Read tool vision per frame). Auto-captions are sufficient — no Whisper dependency.
- [ ] **RESEARCH-08**: Equipboard pages produce `artist_usage` chunks (with verbatim review quotes when present) and `cross_ref` chunks (`used_with`, `similar_in_category`) per the chunk schema.
- [x] **RESEARCH-09**: Cross-source corroboration is automatic — when ingestion notices a chunk references a name (gear/artist/external resource) that another already-ingested chunk also references, set `cross_source_match_candidates` on the chunk.

### CITATION — Cross-source citation tracking

The "watch this video" recommendation feedback loop.

- [ ] **CITATION-01**: Every external URL referenced from any chunk produces an `external_resource` chunk with `{resource_type, creator, title, url, updated, relevance, citing_chunk_ids[]}`.
- [ ] **CITATION-02**: When N (configurable, default 2) sources independently reference the same external resource, surface to the user as "this was referenced N times — worth verifying."
- [ ] **CITATION-03**: User can mark a surfaced resource as verified → triggers ingestion (`/patchbay:research <url>` for articles, multimodal YT pipeline for videos) and promotes the resulting chunks to high-trust.
- [ ] **CITATION-04**: URL canonicalization handles common variants (`youtube.com/watch?v=X` vs `youtu.be/X`, with/without `?si=`, with/without trailing slashes) before counting citations.

## Future Requirements (deferred to v2.x or v3.0)

- **User taste profile** (seed: [user-taste-profile.md](seeds/user-taste-profile.md)) — independent of substrate; needs its own milestone scope
- **Whisper transcription for YouTube** — auto-captions are sufficient for v1; quality upgrade later
- **Bounding-box provenance** — `{source, location_anchor}` is enough for v1; bbox is v2+
- **Tier-2 extension auto-install flow** — production should detect missing extension and surface install hint, but not auto-install
- **Conversational AI / hover-citation UX** — consumer of the substrate, separate skill milestone

## Out of Scope (will not build)

- **Audio plugin / DAW integration** — Patchbay produces markdown artifacts, not audio
- **Multi-gear batch ingest** — one gear at a time per invocation; batch is an orchestration concern
- **Mass scraping of entire sites** — Patchbay is gear-anchored; per-gear ingest only
- **Account-gated content** (private subreddits, paid review sites, anything behind paywall) — out of scope for v2.0; could be revisited if user asks
- **Live web monitoring / re-fetch** — chunks are scraped once, with user-driven refresh; no scheduler

## Traceability

Each REQ-ID maps to exactly one phase. Coverage verified during roadmap creation: **24 / 24** requirements mapped.

| Phase | Requirements |
|-------|--------------|
| Phase 2 — Chunk schema + patchbay:ingest | CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, CHUNK-05, INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06 |
| Phase 3 — patchbay:research with tiered fetch | RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-04, RESEARCH-05, RESEARCH-06, RESEARCH-07, RESEARCH-08, RESEARCH-09 |
| Phase 4 — Citation tracking + recommendations | CITATION-01, CITATION-02, CITATION-03, CITATION-04 |

---
*Last updated: 2026-05-08 — milestone v2.0 (gear-knowledge) traceability filled in during roadmap creation*
