# Roadmap — patchbay-plugin

## Milestones

- ✅ **v1.0 dialed-in** — Phase 1 (shipped 2026-05-07)
- ✅ **v2.0 gear-knowledge** — Phases 2-4 (shipped 2026-05-18)
- 📋 **v3.0** — TBD (run `/gsd-new-milestone` to scope)

## Phases

<details>
<summary>✅ v1.0 dialed-in (Phase 1) — SHIPPED 2026-05-07</summary>

### Phase 1: Build dialed-in skill
**Goal:** Author `skills/dialed-in/SKILL.md` end-to-end so the skill activates and runs against the documented invocation patterns.
**Requirements:** SKILL-01..03, PROC-01..08, DATA-01..03, ERR-01..02, UI-01..02
**Plans:** 1 plan
**Status:** Complete (2026-05-07)

</details>

<details>
<summary>✅ v2.0 gear-knowledge (Phases 2-4) — SHIPPED 2026-05-18</summary>

Archived: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)
Audit: [milestones/v2.0-MILESTONE-AUDIT.md](milestones/v2.0-MILESTONE-AUDIT.md) — 24/24 requirements satisfied, 5/5 E2E flows pass, 138/138 tests green (TECH_DEBT status, non-blocking)
Phases moved to: [milestones/v2.0-phases/](milestones/v2.0-phases/)

- [x] **Phase 2: Chunk schema + patchbay:ingest** (3/3 plans) — completed 2026-05-12. Verified against Boss BF-3.
- [x] **Phase 3: patchbay:research with tiered fetch** (5/5 plans) — completed 2026-05-17. Production smoke verified.
- [x] **Phase 4: Citation tracking + recommendations** (3/3 plans) — completed 2026-05-18. 138/138 tests + goal-backward verifier.

**v2.0 delivered:**
- `patchbay:ingest <gear>` — manual PDF → schema-valid `chunks.jsonl`
- `patchbay:research <gear>` — tiered web ingest (Equipboard, Reddit, articles, YouTube)
- `patchbay:research --review-failures` — interactive escalation, no auto-fallback
- `patchbay:research --citations <gear>` — citation-count recommendations
- `patchbay:research --verify <gear> <url>` — verified-promotion to high-trust
- Unified chunk schema + per-gear knowledge store at `<gear_root>/<Brand Item>/knowledge/chunks.jsonl`

</details>

### 📋 v3.0 (Not yet scoped)

Run `/gsd-new-milestone` to define v3.0 scope and requirements.

**Candidates surfaced during v2.0:**
- Skill rename: `liner-notes` → `rip-off` (cosmetic; light-touch phase)
- CITATION-02 primary-source independence (lift the same-class re-publication under-count limitation)
- Conversational AI front-end on the gear-knowledge substrate (hover-citation UX consumer)
- A `patchbay:soundcheck` skill (or similar) that consumes both `chunks.jsonl` stores at once
- Multi-gear tone-graph queries / cross-gear recommendations

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Build dialed-in skill | v1.0 | 1/1 | Complete | 2026-05-07 |
| 2. Chunk schema + patchbay:ingest | v2.0 | 3/3 | Complete (VERIFIED) | 2026-05-12 |
| 3. patchbay:research with tiered fetch | v2.0 | 5/5 | Complete (VERIFIED) | 2026-05-17 |
| 4. Citation tracking + recommendations | v2.0 | 3/3 | Complete (VERIFIED) | 2026-05-18 |

## Out of Scope (project-level)

- Whisper transcription for YouTube — auto-captions sufficient (validated spike 002a/002c); quality upgrade not worth the dependency.
- Tier-2 extension auto-install flow — production detects `[]` from `list_connected_browsers` and surfaces install hint, no auto-install.
- Bounding-box provenance — `{source, location_anchor}` is sufficient; bbox is a future precision upgrade.

---
*Last updated: 2026-05-18 — v2.0 (gear-knowledge) milestone shipped*
