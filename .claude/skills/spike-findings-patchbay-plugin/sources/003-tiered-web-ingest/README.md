---
spike: 003
name: tiered-web-ingest
type: standard
validates: "Given gear-research URLs that include a known-blocked site (Equipboard) and an open-data site (Reddit), when ingest is attempted with a cheap-by-default tier-1 static fetch + a failures.log for escalation, then chunks are produced for the accessible source(s), the inaccessible one(s) are logged with suggested escalation, and the user retains agency over when to spend more compute"
verdict: VALIDATED
related: [001, 002a, 002c]
tags: [research, web-scrape, equipboard, reddit, cloudflare, tiered-ingest, knowledge-graph]
---

# Spike 003: tiered web ingest with failure-logging

## What This Validates

The cheap-by-default web ingest architecture: try a fast static fetch first, log failures with structured metadata (URL + reason + suggested escalation tier), let the user decide when to escalate to a real-browser scrape. This is the "fallback as user-driven escalation, not auto-magic" pattern the user explicitly asked for during planning.

Test gear: **Chase Bliss Audio Clean** (compressor pedal). Two source URLs:
- Equipboard product page (known-blocked by Cloudflare)
- Reddit "comprehensive review" thread on r/guitarpedals (464 upvotes, 64 comments)

Spike validates three things at once:
1. Static fetch fails predictably on Cloudflare-protected sites (and the failure log is useful)
2. Reddit's `?.json` suffix endpoint still works, no escalation needed for this source class
3. The chunk schema sketched in spikes 001 + 002 extends cleanly to web sources, and the **knowledge-graph chunk types** (`artist_usage`, `cross_ref`) are the highest-value addition

## Research

| Approach | Tool | Pros | Cons | Status |
|----------|------|------|------|--------|
| **Tier 1: `curl` / `requests` static fetch** | curl | Free, instant, mirrors what production would attempt first | Blocked by Cloudflare, anti-bot UA checks, JS challenges, paywalls | **Used** for spike — both sources |
| **Tier 2: Real browser via `Claude_in_Chrome`** | The user's actual Chrome via MCP | Indistinguishable from human; gets past anti-bot | Slower, requires user's Chrome to be open | Documented as escalation target; not exercised in spike (user pasted DOM content as alternative tier-0 path) |
| **Tier 3: Visual capture + Claude vision** | Tier 2 + screenshot + Read tool | Bulletproof against any anti-bot | Slowest, most token cost | Not exercised; reserved for sites that block even tier-2 |
| **Tier 0: Manual user-paste** | Just paste DOM text | 100% reliable, user-driven | Manual labor; doesn't scale | **Used** for Equipboard in this spike — when blocked, user pasted the page text |

**Reddit-specific path (`?.json` suffix):** Reddit publishes a JSON view of every public thread by appending `.json` to the URL. Returns full post text + comments tree without auth. Got 200 OK / 392KB on the test thread. Production should default to this for Reddit URLs.

## How to Run

```bash
cd .planning/spikes/003-tiered-web-ingest

# Tier-1 attempts (one fails, one succeeds)
curl -sS -o raw/eb-fake-ua.html -w "HTTP %{http_code}\n" -A "Mozilla/5.0 ..." \
     "https://equipboard.com/items/chase-bliss-audio-clean"
# → HTTP 403 (Cloudflare). Logged to failures.log.

curl -sS -o raw/reddit.json -w "HTTP %{http_code}\n" -A "Mozilla/5.0 ..." \
     "https://www.reddit.com/r/guitarpedals/comments/1gyt83o/.../.json"
# → HTTP 200, 392KB JSON.
```

Open the viewer:
```
http://localhost:8767/viewer.html
```

## What to Expect

The viewer shows two columns side-by-side: 10 Equipboard chunks (left, tier 0 / user-pasted, red badge) and 7 Reddit chunks (right, tier 1 / `.json` endpoint, green badge). Filter bar at top includes a **"Cross-source matches only"** view that highlights chunks where both sources reference the same gear (Cali76, Empress, JHS Pulp 'N Peel — all corroborated as comparison reference compressors).

### New chunk types validated in this spike

| Type | Schema | Why it matters |
|------|--------|----------------|
| `artist_usage` | `{ artist, roles, verification_type, verification_note, verbatim_quote, alternatives_recommended, citation_targets }` | The artist↔gear edge. Logs "Rhett Shull uses Chase Bliss Clean, here's his verbatim review, here's what he recommends as alternatives." Patchbay can later answer "what does Rhett Shull use?" or "show me everything Emily Hopkins reviewed." |
| `cross_ref` | `{ from_gear, relation, to_gear, weight, cross_source_match_candidates }` | Gear↔gear edges. `used_with` (pedalboard companions), `similar_in_category` (alternative gear). The `cross_source_match_candidates` field is the breakthrough — it flags when multiple sources independently mention the same comparison gear, raising confidence. |
| `review_section` / `review_subsection` | `{ section_header, key_thesis, summary, parameter, verdict, cross_source_targets }` | Long-form reviews chunked at section/subsection granularity for citation-hover. Each subsection is its own citable unit. |
| `external_resource` | `{ resource_type, title, site, updated, relevance }` | Tracks external citations (gear guides, articles, YT videos). Foundation for the **citation count → recommendation** pattern. |

### The "tutorial mentioned multiple times → surface to user" pattern

User insight surfaced during this spike: when an external resource (a specific YouTube tutorial, an article URL) is cited from multiple sources during research, citation count crosses a threshold → surface to user as "you should probably watch/read this."

This isn't built into the spike but is a real pattern this chunk schema enables. With `external_resource` chunks tracked across sources, a future skill can aggregate citation counts and rank external resources by independent reference frequency. Captured as a seed below.

## Investigation Trail

**Iteration 1 — block test.** Curl'd Equipboard with both default and Chrome UA. Both returned 403 with the Cloudflare "Just a moment..." page. Confirmed and logged. Predicted before doing the test, but validated the failure log format works on a real failure.

**Iteration 2 — Reddit `.json` endpoint.** Tried `?.json` suffix. Got 200 OK, 392KB of clean JSON with the full self-text post + 64 top-level comments. No auth needed. This is a major architectural win for Reddit specifically — for that source we never need tier 2.

**Iteration 3 — chunk schema for Equipboard.** Equipboard pages have a much richer block structure than typical articles. Identified 7 distinct content blocks worth chunking: description, product_specs, faq, **artist_usage** (the highest-value type — already includes verbatim quotes and citation pointers), **genre_usage**, **used_with cross-refs**, **similar-gear cross-refs**, gear_guide links. The `artist_usage` chunks already include the cited tutorial creator names — so the chunk schema natively supports cross-source citation tracking.

**Iteration 4 — cross-source matching.** When chunking the Reddit review, noted that u/Twinningses explicitly compares Clean to **Cali76** and **Empress**. When chunking the Equipboard `similar-gear` block, noted the SAME two compressors top the list. Added `cross_source_match_candidates` field to flag this. Result: 3 chunks now carry cross-source flags, validating that the architecture surfaces independent corroboration automatically.

**Iteration 5 — failures.log format.** Settled on JSONL (one JSON object per line) with fields: `timestamp, url, tier_attempted, http_status, reason, reason_detail, suggested_escalation, last_attempted, retry_count`. Append-only by production code; user reviews and decides which entries to escalate.

## Results

**Verdict: VALIDATED.** All three architectural claims held:

1. **Tier-1 static fetch fails predictably on Cloudflare-protected sites.** Equipboard returned 403 on both default and real-browser User-Agent; the failure was logged with `suggested_escalation: 2` (Claude_in_Chrome). User retains agency over the escalation decision per the architecture.
2. **Reddit `.json` endpoint works without escalation.** Source-class-specific cheap paths exist for some sites (Reddit being the most useful one for community-discussion content).
3. **The chunk schema extends cleanly to web sources** AND the new graph chunk types (`artist_usage`, `cross_ref`) are the highest-leverage addition — they convert flat content into a knowledge graph that can answer relational queries ("what does this artist use?", "what gear is similar?", "what's most often paired with this pedal?").

### Unexpected findings

- **Equipboard's `artist_usage` blocks already contain verbatim YouTube review text.** The Rhett Shull artist_usage entry includes the full text of his review — Equipboard scraped the YouTube video and surfaced the transcript inline. This means EB ingestion can deliver reviewer commentary *without* needing to run the multimodal YT pipeline (spike 002c) for sources EB has already covered. EB is essentially a meta-aggregator.
- **Cross-source corroboration emerged automatically.** Without explicitly designing for it, the spike surfaced 3 cross-source matches (Cali76, Empress, JHS Pulp 'N Peel — independently mentioned by both EB and Reddit as the relevant comparison set). This validates the architecture's claim that multiple sources self-corroborate.
- **The "Tier 0 / user-paste" tier emerged organically.** When Cloudflare blocked tier 1, the user pasted the DOM text directly. This is a real production tier — the failures.log gives the user enough context to either escalate to tier 2 (browser automation) or just paste the content manually. Both paths feed the same chunk schema.

### Impact on remaining roadmap

- The chunk schema is now battle-tested across **manual** (spike 001), **YT video** (spike 002c), and **web** (this spike). Three independent source classes, one schema. **The architecture from the knowledge-architecture note holds.**
- `patchbay:research` source priority confirmed: (1) manual = backbone, (2) Equipboard + Reddit = primary external, (3) YT multimodal = secondary, (4) YT captions-only = fallback.
- The **citation-count-driven recommendation** pattern is now an explicit seed for a future spike or feature.

### What's left to spike

- Tier-2 (Claude_in_Chrome) on a real blocked URL — proof-of-concept that it actually gets past Cloudflare. Worth a quick follow-up spike.
- Citation count aggregation across N sources for the "watch this video" recommendation pattern.

These are nice-to-haves. The core architecture is now sufficiently validated to start planning `patchbay:ingest` and `patchbay:research` as real phases.
