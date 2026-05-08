# Spike Wrap-Up Summary

**Date:** 2026-05-08
**Spikes processed:** 4
**Feature areas:** Chunk schema · Manual ingestion · YouTube ingestion · Web scraping · Spike pattern (template)
**Skill output:** [`.claude/skills/spike-findings-patchbay-plugin/`](../../.claude/skills/spike-findings-patchbay-plugin/)

## Processed Spikes

| # | Name | Type | Verdict | Feature Area |
|---|------|------|---------|--------------|
| 001 | vision-quality-pedal-manual | standard | ✓ VALIDATED | Manual ingestion + chunk schema |
| 002a | yt-captions-only | comparison | ⚠ PARTIAL | YouTube ingestion (fallback layer) |
| 002c | yt-multimodal-sampled | comparison | ✓ VALIDATED (secondary) | YouTube ingestion + chunk schema |
| 003 | tiered-web-ingest | standard | ✓ VALIDATED | Web scraping + knowledge-graph chunk types |

## Key Findings

### Architecture is locked-in

Three independent source classes (PDF manual, YouTube video, web pages) all serialize to the same chunk schema. The architecture from [`.planning/notes/knowledge-architecture.md`](../notes/knowledge-architecture.md) — gear-anchored, citation-traceable, provenance per chunk — holds across every source class tested.

### Native Claude tools are the production path

- Manual ingestion → Read tool's PDF support (up to 20 pages/call, native vision).
- YouTube multimodal → ffmpeg samples frames, Read tool describes them. Same vision pipeline as manual ingest, different input source.
- Web scraping → tier-1 `requests`/`curl` for cheap fetches; tier-2 `Claude_in_Chrome` MCP for blocked sites. Each tier maps to existing infrastructure; no new runtimes.

### Knowledge-graph chunk types are higher-leverage than flat content

`artist_usage` (gear↔artist edges with verification source) and `cross_ref` (gear↔gear `used_with` / `similar_in_category` edges) emerged as the highest-leverage additions to the chunk schema. They convert flat content into queryable relations: "what does Rhett Shull use?", "what's most often paired with Chase Bliss Clean?", "what compressors are similar?".

### Cross-source corroboration is emergent

Without explicit design, spike 003 surfaced 3 cross-source matches (Cali76, Empress, JHS Pulp 'N Peel — independently referenced by both Equipboard's similar-gear list and the Reddit review's comparison points). The schema's `cross_source_match_candidates` field captures this for free as ingestion proceeds.

### Equipboard is a meta-aggregator

Equipboard's `artist_usage` blocks already include verbatim text from YouTube reviews (e.g., Rhett Shull's full Chase Bliss Clean review, transcribed and surfaced inline). EB ingest delivers reviewer commentary without running the spike-002c multimodal pipeline for sources EB has already covered. This reorders source priority: EB provides transitive YT content for free.

### YouTube is secondary

User's source priority order, locked in after spike 002 verification: (1) Manual = backbone, (2) Web articles/reviews = primary external, (3) YouTube multimodal = secondary reference, (4) YouTube captions-only = fallback. YouTube *is* useful — especially for technique demos where seeing the host's hands matters — but it's not the primary research substrate.

### Cheap-by-default + user-driven escalation works

Spike 003's tiered architecture (try cheap fetch → log failures with structured metadata → user reviews and decides which to escalate) is the right shape for `patchbay:research`. Cost stays bounded; the user retains agency over when to spend more compute.

### "Tier 0 / user-paste" is a real production tier

When tier-1 blocks, the user pasting DOM content is a valid path — same chunk schema, just different `tier_label` in provenance. Documented in the failure log so the user can choose between tier-2 escalation and tier-0 paste.

### Citation-count → recommendation is a free emergent feature

User insight surfaced during spike 003: when an external resource (a specific YouTube tutorial, an article URL) is referenced from multiple ingested sources, the AI should surface it as "worth verifying." Captured as a seed at [`.planning/seeds/citation-count-recommendations.md`](../seeds/citation-count-recommendations.md). Trivial to build once `patchbay:research` ships — it's just a SQL group-by on the chunk store.

## What's left to spike (deferred / nice-to-have)

- **Tier-2 (Claude_in_Chrome) end-to-end on a real blocked URL** — opened as spike 003b; runnable when user installs the Chrome extension. Not blocking.
- **Whisper-vs-captions quality comparison** for YouTube — only matters if 002c's quality is insufficient at scale, which it wasn't for the spike's test video.
- **Citation-count aggregation** — already specified as a seed; build alongside `patchbay:research`.

These are nice-to-haves. The core architecture is sufficiently validated to start planning `patchbay:ingest` and `patchbay:research` as real phases.

## Appendix — spike 003c added 2026-05-08 (after initial wrap-up)

User asked whether tier-2 (Claude_in_Chrome) AND tier-3 (computer-use) could both be supported for flexibility. Spike 003c proved tier-3 works end-to-end against the same Cloudflare-blocked Equipboard URL that spike 003 logged in `failures.log`.

**Verdict: VALIDATED.** Tier-3 escalation:
- Bypasses Cloudflare entirely (page renders fully in user's real Chrome)
- Requires only per-session `request_access` for Chrome (no extension install)
- Captures content lower tiers miss — knob labels printed on the pedal product photo (DYNAMICS, SENSITIVITY (RAMP), WET, ATTACK, EQ, DRY, RELEASE, MODE, PHYSICS, AUX, BYPASS) — purely visual content not in the DOM text
- Constraint: read-tier Chrome can't scroll programmatically; user scrolls between screenshots for below-fold content. The constraint is the architecture working as designed.

**Architectural addition:** `failures.log` `suggested_escalation` field expands to `2 | 3 | "either" | "manual-paste" | "skip"`. Tier 2 and tier 3 are both first-class — they have different failure modes (tier 2: extension automation can be detected; tier 3: bulletproof but slower). Production should support both and let the user choose.

Spike 003b (`Claude_in_Chrome` end-to-end) remains OPEN — runnable when the user has the extension installed. The web-scraping reference in the skill now documents both tiers fully.

## Appendix — spike 003b added 2026-05-08 (after 003c — completes the tier ladder)

User installed the Claude in Chrome extension and re-ran spike 003b for real. **Verdict: VALIDATED.**

Tier-2 returned the **entire DOM in a single `get_page_text` call** — structured plain text, ~10KB cleaned, covering every section of the Equipboard page in ~10 seconds end-to-end.

**The real architectural finding from the side-by-side:**

Tier 0 (user-paste) — which looked complete in spike 003 — turned out to be **substantially incomplete** when compared against tier 2's full DOM:
- Tier 0 missed 6 of 8 videos (only Rhett Shull's was in the pasted excerpt)
- Tier 0 missed ALL 3 critic reviews with their full text (compressorpedalreviews.com, guitarworld.com, gearnews.com)
- Tier 0 missed the "Used With" category rollup
- Tier 0 missed page metadata (added-by user, gear IQ, add date)

This **demoted tier 0 to "last-resort escape hatch"** in the architecture. Production should always prefer tier 2 when the extension is connected; tier 0 is for sessions where neither tier 2 nor tier 3 is set up.

**Tier 2 + Tier 3 are complementary, not redundant.** Tier 2 captures structured DOM but NOT image-embedded text (knob labels printed on product photos, screen states in tutorial screenshots). Tier 3 (003c) captures those via vision but is viewport-limited and slow. **Recommended production primary path: tier 2 first, optional tier 3 follow-up for image-rich pages.**

**Citation-count seed gets real data:** the 8 videos with creator+title pairs from tier 2's DOM extraction are exactly what the seed at [`.planning/seeds/citation-count-recommendations.md`](../seeds/citation-count-recommendations.md) needs to test against. With 3 critic reviews on external domains and 8 videos with creators, the citation aggregator has a real corpus to develop on.

**The fetch tier ladder is now end-to-end-validated:**

| Tier | Status | When to use |
|------|--------|-------------|
| 1 — static fetch | ✓ 003 (failure mode confirmed on Cloudflare) | Always try first; cheap |
| 2 — Claude_in_Chrome | ✓ **003b** | Primary escalation when extension installed; gold-standard DOM extraction |
| 3 — computer-use + vision | ✓ 003c | Tier-2 unavailable, OR image-rich page where image text matters |
| 0 — user-paste | ✓ 003 | Last-resort escape hatch when 2 and 3 are both unavailable |

## Routing for future conversations

The skill at [`.claude/skills/spike-findings-patchbay-plugin/`](../../.claude/skills/spike-findings-patchbay-plugin/) auto-loads in implementation work via the routing line in [CLAUDE.md](../../CLAUDE.md). Future build sessions read the SKILL.md + relevant references and don't need to re-derive these decisions.
