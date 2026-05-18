# Roadmap — patchbay-plugin

## Milestones

- ✅ **v1.0 dialed-in** — Phase 1 (shipped 2026-05-07)
- 🚧 **v2.0 gear-knowledge** — Phases 2-4 (in progress)

## Overview

v2.0 builds the gear-knowledge substrate so downstream skills (and the eventual conversational AI) can answer hover-citable questions about the user's gear. The architecture was pre-validated across six spikes (001 / 002a / 002c / 003 / 003b / 003c). The chunk schema is locked, fetch-tier ladder is locked, source-class blueprints are written. This roadmap is a clean execution plan that turns those validated patterns into shipped skills in dependency order: schema scaffolding + manual ingest first (proves the schema in production code against the simplest source class), tiered web research second (extends the same schema across four more source classes), citation tracking last (consumes the `external_resource` chunks both prior phases produce).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work — continuous numbering across milestones
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>✅ v1.0 dialed-in (Phase 1) — SHIPPED 2026-05-07</summary>

### Phase 1: Build dialed-in skill
**Goal:** Author `skills/dialed-in/SKILL.md` end-to-end so the skill activates and runs against the documented invocation patterns.
**Requirements:** SKILL-01..03, PROC-01..08, DATA-01..03, ERR-01..02, UI-01..02
**Plans:** 1 plan
**Status:** Complete (2026-05-07)

</details>

### 🚧 v2.0 gear-knowledge (In Progress)

**Milestone Goal:** Ship `patchbay:ingest`, `patchbay:research`, the unified chunk schema + per-gear knowledge store, and the citation-count recommendation feedback loop.

- [x] **Phase 2: Chunk schema + patchbay:ingest** — Lock the load-bearing chunk schema in production code and ship `/patchbay:ingest` for manual PDFs (the simplest source class). **Shipped 2026-05-12. Verified against Boss BF-3.**
- [ ] **Phase 3: patchbay:research with tiered fetch** — Ship `/patchbay:research` covering web articles, Reddit, Equipboard, and YouTube via the cheap-by-default + user-driven escalation tier ladder.
- [ ] **Phase 4: Citation tracking + recommendations** — Aggregate `external_resource` chunks across sources and surface "watch this" recommendations once an external URL is referenced N times.

## Phase Details

### Phase 2: Chunk schema + patchbay:ingest
**Goal:** User can run `/patchbay:ingest <gear>` against a manual PDF and get a populated, schema-valid `chunks.jsonl` for that gear in the per-gear knowledge store.
**Depends on:** Nothing (first phase of v2.0; consumes spike-findings-patchbay-plugin skill)
**Requirements:** CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, CHUNK-05, INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06
**Success Criteria** (what must be TRUE):
  1. User can run `/patchbay:ingest <gear>` against `<gear_root>/<Brand Item>/manuals/*.pdf` and find a populated `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` (one chunk per line, append-only) when the command completes.
  2. Every chunk in the file carries the unified shape — `id`, `type`, `source`, `content`, and a `provenance` block with `manual`, `page`, `rough_region`, and `scraped_at` — so a citation-hover UX can deep-link any chunk back to its manual page.
  3. Every image in the manual produces an `image` chunk with one of the seven `image_category` values; no images are skipped or filtered.
  4. Each manual page produces 1-4 chunks split by content block (text section vs image vs control close-up), and multi-page manuals (>20 pages) ingest cleanly with no gaps where the Read-tool batch boundaries fall.
  5. Re-running `/patchbay:ingest` on a gear that already has chunks shows a diff and asks the user to confirm before overwriting; user-edited chunks (whether edited directly in `chunks.jsonl` or via a per-chunk markdown export) survive the re-ingest.
  6. The schema supports `artist_usage`, `cross_ref`, and `external_resource` chunk types as additive fields so Phase 3 and Phase 4 can write the same JSONL file without further schema changes.
**Plans:** 3 (01-schema-reference → 02-skill-body → 03-verify; sequential)
**UI hint:** no (skill outputs are JSONL + markdown only; UI rendering is a future milestone)

### Phase 3: patchbay:research with tiered fetch
**Goal:** User can run `/patchbay:research <gear>` and get web articles, Reddit threads, Equipboard pages, and YouTube videos ingested into the gear's `chunks.jsonl` via the cheap-by-default + user-driven escalation tier ladder.
**Depends on:** Phase 2 (consumes the locked chunk schema and the per-gear knowledge store)
**Requirements:** RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-04, RESEARCH-05, RESEARCH-06, RESEARCH-07, RESEARCH-08, RESEARCH-09
**Success Criteria** (what must be TRUE):
  1. User can run `/patchbay:research <gear>` and find new chunks appended to `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` from at least four source classes (web articles, Reddit, Equipboard, YouTube), each chunk carrying its tier-of-origin in `tier_used` and a deep-link in provenance.
  2. Tier-1 static fetch is attempted first for every URL; on HTTP non-2xx or detected anti-bot challenge, an entry appears in `failures.log` (append-only JSONL, schema-conformant) — no automatic fallback to tier 2 or 3.
  3. User can run `/patchbay:research --review-failures`, see each logged failure with its `suggested_escalation` (`2 | 3 | "either" | "manual-paste" | "skip"`), and choose per-entry whether to escalate to tier 2, tier 3, paste manually, or skip; tier-2 escalation prechecks `mcp__Claude_in_Chrome__list_connected_browsers` and surfaces install instructions when the result is `[]` rather than failing silently.
  4. Reddit URLs hit the `?.json` cheap path automatically at tier 1 with no escalation required; Equipboard pages produce `artist_usage` chunks (with verbatim review quotes when present) and `cross_ref` chunks (`used_with`, `similar_in_category`); YouTube URLs ingest multimodally (yt-dlp captions + `parse_vtt.py` + ffmpeg frame sampling at 30s + Read-tool vision per frame) without a Whisper dependency.
  5. When ingestion notices a chunk references a name (gear / artist / external resource) that another already-ingested chunk references, the new chunk has its `cross_source_match_candidates` field populated automatically — corroboration is emergent, not manually wired.
**Plans:** 5 plans
Plans:
**Wave 1**
- [x] 03-01-PLAN.md — Tier-1 fetch core + failures.log writer + URL router + chunk writer w/ cross-source emergence (RESEARCH-01/02/03/09)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 03-02-PLAN.md — Source class: Reddit `.json` cheap path (RESEARCH-06)
- [x] 03-03-PLAN.md — Source class: Equipboard `artist_usage` + `cross_ref` chunks (RESEARCH-08)
- [x] 03-04-PLAN.md — Source class: YouTube multimodal (yt-dlp + parse_vtt + ffmpeg + Read vision; no Whisper) (RESEARCH-07)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 03-05-PLAN.md — `--review-failures` interactive flow + tier-2 precheck + tier-3 vision (RESEARCH-04/05/09)
**UI hint:** no (skill outputs are JSONL + markdown only; UI rendering is a future milestone)

### Phase 4: Citation tracking + recommendations
**Goal:** Every external URL referenced from any chunk produces an `external_resource` chunk, and when N independent sources reference the same URL the user is surfaced "this was referenced N times — worth verifying" with a path to verify and ingest it.
**Depends on:** Phase 3 (needs `external_resource` chunks produced by web + YouTube ingestion)
**Requirements:** CITATION-01, CITATION-02, CITATION-03, CITATION-04
**Success Criteria** (what must be TRUE):
  1. After running `/patchbay:research <gear>`, every external URL referenced from any chunk has a corresponding `external_resource` chunk in `chunks.jsonl` with `{resource_type, creator, title, url, updated, relevance, citing_chunk_ids[]}` populated — no manual aggregation step required.
  2. URL canonicalization handles the common variants (`youtube.com/watch?v=X` ↔ `youtu.be/X`, with/without `?si=`, with/without trailing slashes) so two chunks pointing at the same video count as one citation, not two.
  3. When N (configurable, default 2) independent sources reference the same canonicalized URL, the user sees a surfaced recommendation listing the resource and the citing chunks — the citation-count threshold is observable from the user's terminal output, not buried in a log.
  4. User can mark a surfaced resource as verified, which triggers ingestion (`/patchbay:research <url>` for articles, the multimodal YT pipeline for videos) and promotes the resulting chunks to high-trust in the knowledge store.
**Plans:** 3 plans
Plans:
**Wave 1**
- [x] 04-01-PLAN.md — URL canonicalization + post-write external_resource sweep (CITATION-01, CITATION-04)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 04-02-PLAN.md — `/patchbay:research --citations <gear>` recommendation surface (CITATION-02)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 04-03-PLAN.md — `/patchbay:research --verify <gear> <url>` verified-promotion flow (CITATION-03)
**UI hint:** no (skill outputs are JSONL + markdown only; UI rendering is a future milestone)

## Progress

**Execution Order:**
Phases execute in numeric order: 2 → 3 → 4

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Build dialed-in skill | v1.0 | 1/1 | Complete | 2026-05-07 |
| 2. Chunk schema + patchbay:ingest | v2.0 | 3/3 | Complete (VERIFIED) | 2026-05-12 |
| 3. patchbay:research with tiered fetch | v2.0 | 0/5 | Planned | - |
| 4. Citation tracking + recommendations | v2.0 | 0/3 | Planned | - |

## Coverage

All 24 v2.0 requirements map to exactly one phase. No requirements are unmapped, no requirements are double-mapped.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 2. Chunk schema + patchbay:ingest | CHUNK-01, CHUNK-02, CHUNK-03, CHUNK-04, CHUNK-05, INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06 | 11 |
| 3. patchbay:research with tiered fetch | RESEARCH-01, RESEARCH-02, RESEARCH-03, RESEARCH-04, RESEARCH-05, RESEARCH-06, RESEARCH-07, RESEARCH-08, RESEARCH-09 | 9 |
| 4. Citation tracking + recommendations | CITATION-01, CITATION-02, CITATION-03, CITATION-04 | 4 |
| **Total** | | **24 / 24** ✓ |

## Out of milestone

- User taste profile (deferred to a future milestone; seed at `seeds/user-taste-profile.md`)
- Whisper transcription for YouTube (auto-captions sufficient for v2; quality upgrade later)
- Bounding-box provenance (`{source, location_anchor}` is sufficient for v2)
- Tier-2 extension auto-install flow (production should detect `[]` and surface install hint, not auto-install)
- Conversational AI / hover-citation UX (consumer of this substrate, separate skill milestone)

---
*Last updated: 2026-05-17 — Phase 4 planned (3 plans, 3 waves)*
