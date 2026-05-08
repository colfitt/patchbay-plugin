---
spike: 003b
name: tier2-claude-in-chrome-escalation
type: comparison
validates: "Given a URL that tier-1 static fetch returned 403 on (Cloudflare-blocked Equipboard), when the user has installed the Claude in Chrome extension and the spike uses the Claude_in_Chrome MCP to navigate + get_page_text, then the full DOM content is returned in a single call, capturing sections that tier-0 user-paste and tier-3 viewport-screenshot both miss"
verdict: VALIDATED
related: [003, 003c]
tags: [research, web-scrape, equipboard, cloudflare, tier-2, claude-in-chrome, escalation]
---

# Spike 003b: tier-2 escalation via Claude_in_Chrome

## What This Validates

The companion spike to 003c. Spike 003 documented Equipboard's Cloudflare block; 003c proved tier-3 (computer-use + vision) works as fallback. This spike proves **tier-2 is the gold standard when the extension is connected** — full DOM in one call, structured, fast.

The whole tier ladder is now validated end-to-end:

| Tier | Status | What it captures | Cost |
|------|--------|------------------|------|
| 0 (manual paste) | ✓ 003 | Whatever user copy-pastes — selective, often incomplete | Manual |
| 1 (static fetch) | ✓ 003 (failure mode) | 403 on Cloudflare-protected sites | Free |
| 2 (Claude_in_Chrome) | ✓ **003b** | **Full DOM in one call** — every section | Free after one-time extension install |
| 3 (computer-use + vision) | ✓ 003c | Viewport-only; captures image-embedded text (knob labels, screen states) | Per-session permission grant |

## How to Run

**Prerequisite:** Claude in Chrome extension installed in user's Chrome and Connect clicked. `mcp__Claude_in_Chrome__list_connected_browsers` should return at least one entry.

```python
# 1. Select the connected browser
mcp__Claude_in_Chrome__select_browser(deviceId="...")

# 2. Get tab context (or create a new one)
mcp__Claude_in_Chrome__tabs_context_mcp(createIfEmpty=True)

# 3. Batch navigate + wait + screenshot for confidence (optional)
mcp__Claude_in_Chrome__browser_batch(actions=[
    {"name": "navigate", "input": {"tabId": ..., "url": "https://equipboard.com/items/..."}},
    {"name": "computer", "input": {"tabId": ..., "action": "wait", "duration": 4}},
    {"name": "computer", "input": {"tabId": ..., "action": "screenshot"}},
])

# 4. Pull the full DOM text (the actual ingest call)
mcp__Claude_in_Chrome__get_page_text(tabId=...)
```

This was the entire spike — three MCP calls. ~10 seconds end-to-end including page load.

## What to Expect

`get_page_text` returns the full main-element content as plain text, structured (preserves headings, lists, paragraph breaks). For Equipboard's Chase Bliss Clean page that's ~10KB cleaned, covering every page section the producer needed:

- Breadcrumb navigation
- Title, price, price tier, critic review count, store CTAs
- Social proof strip (artists, setups, wishlisted, saved, last updated)
- Pricing & availability table
- Description paragraphs + Key Features list
- Product specs (brand/model/finish/year/made-in/categories/format)
- 5 FAQs with full Q&A
- **8 videos with creator names AND titles** (only Rhett Shull was in the user-paste version!)
- **3 critic reviews with full text + source domains** (user-paste showed "0 critic reviews" because the user pasted only a sub-section)
- Artist usage with verbatim quotes (3 artists)
- Genre usage weights
- Used With (individual gear + category rollup)
- Community setups with contributor Gear IQ scores
- Similar gear (top 40 in category)
- Gear guide links
- Page metadata (added by, gear IQ, dates)

## Investigation Trail

**Iteration 1 — extension prereq.** First attempt at 003c was actually meant to be 003b. `list_connected_browsers` returned `[]` — extension not installed. Pivoted to 003c (computer-use). After 003c committed, user installed and connected the extension; came back to run 003b for real.

**Iteration 2 — connection flow.** `list_connected_browsers` returned 1 browser ("Browser 1", macOS, local). `select_browser(deviceId=...)` returned "Connected to browser 'Browser 1'." `tabs_context_mcp(createIfEmpty=true)` opened a fresh tab.

**Iteration 3 — batch navigation.** Used `browser_batch` per the runtime hint to combine navigate + wait + screenshot in one call. ~5 seconds end-to-end including 4-second sleep. Page rendered fully — no Cloudflare challenge (same as tier 3).

**Iteration 4 — full DOM extraction.** `get_page_text` returned the entire page content cleanly structured. This is the **architectural payoff** — what tier 0 took user effort to paste (and produced an incomplete result) and tier 3 took a screenshot (and was viewport-limited), tier 2 produces in one MCP call.

**Iteration 5 — comparison against tiers 0 and 3.** Side-by-side comparison surfaced major gaps in the lower-tier captures:
- 6 of 8 videos missing from tier-0 paste
- All 3 critic reviews missing from tier-0 paste (the user pasted "0 critic reviews" because they only highlighted the rating-summary subsection)
- "Used With" category rollup missing from tier-0 paste
- Page metadata (creator, IQ score, add date) missing from tier-0 paste
- Knob labels on pedal photo present in tier-3 vision capture but absent from tier-2 DOM (because they're image-embedded text)

## Results

**Verdict: VALIDATED.** Tier-2 escalation works end-to-end, returns the full DOM in a single call, and captures content that tiers 0 and 3 both miss.

### Verified findings

- **Tier 2 is the gold standard when available.** ~10s end-to-end, single API call, complete structured DOM. No image-content (knob labels printed on photos) but otherwise comprehensive.
- **Tier 0 (user-paste) is not a substitute for tier 2.** It LOOKED comprehensive in spike 003, but a side-by-side comparison reveals the user pasted what they highlighted — missing 3 entire critic reviews, 6 of 8 videos, and several structured cross-refs. **Tier 0 should be a last-resort escape hatch, not a routine path.**
- **Tier 2 + Tier 3 are complementary, not redundant.** Tier 2 captures structured DOM but not image-embedded text. Tier 3 captures visual content but is viewport-limited and slow. Combining them gives the most complete picture: tier 2 for structure, tier 3 for image-text content.
- **Citation-count seed gets real data.** The 8 videos discovered in tier 2 have creator + title pairs that the citation-count → recommendation seed needs. Rhett Shull's video is now tracked across `artist_usage` (with verbatim quote) AND `external_resource` (in the videos list) — citation count of 2 from a single source. With 3 critic reviews on external domains (compressorpedalreviews.com, guitarworld.com, gearnews.com), more citation-tracking sources are available.

### Surprises

- **The GuitarWorld review quotes a $469 price**, while the Equipboard page lists $350. Production needs to handle price discrepancies between reviews (which reference launch/list prices) and current page prices. Worth flagging in chunk metadata when detected.
- **The "Harp Lady" video creator on Equipboard is almost certainly Emily Hopkins** (verified harp player in `artist_usage`). Production may want to canonicalize creator handles ↔ artist names to avoid double-counting in citation aggregation.

### Architecture additions

- **Tier 0 (user-paste) demoted to "last-resort"** — primary tier-failure path is now: tier 1 → log failure → suggest tier 2 (if extension connected) or tier 3 (if user OK with vision-token cost) → tier 0 only when both 2 and 3 are unavailable.
- **Tier 2 + Tier 3 hybrid** is the strongest production path for image-rich pages. Tier 2 first for structured DOM; if image-embedded text matters (product photos with control labels, screen-state demos), do a follow-up tier-3 vision pass.
- **Citation aggregation now has real data to test against.** The seed at `.planning/seeds/citation-count-recommendations.md` can be implemented and tested using the 003b chunk output.
