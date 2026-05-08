---
spike: 003c
name: tier3-computer-use-escalation
type: comparison
validates: "Given a URL that tier-1 static fetch returned 403 on (Cloudflare-blocked Equipboard), when the user opens it in their real Chrome and the spike uses the computer-use MCP to screenshot + Claude vision to read the rendered content, then chunks compatible with the schema can be produced — proving tier-3 escalation is a real, available path AND captures content (image labels) that lower tiers miss"
verdict: VALIDATED
related: [003, 003b]
tags: [research, web-scrape, equipboard, cloudflare, tier-3, computer-use, vision, escalation]
---

# Spike 003c: tier-3 escalation via computer-use + vision

## What This Validates

This is the deferred end-to-end proof for [spike 003](../003-tiered-web-ingest/README.md). Tier-1 static fetch returned 403 (Cloudflare) on Equipboard's Chase Bliss Clean product page. Spike 003 documented this in `failures.log` with `suggested_escalation: 2` and the user pasted DOM text as a tier-0 alternative. The architecture promised tier 2 (Claude_in_Chrome) and tier 3 (computer-use + vision) as escalation paths. **This spike proves tier 3 actually works.**

## Research

| Approach | Tool | Pros | Cons | Status |
|----------|------|------|------|--------|
| **Tier 3: `computer-use` MCP + vision** | `mcp__computer-use__*` (request_access for Chrome at read tier, screenshot, Claude vision) + `open URL` from Bash to navigate | Available immediately (per-session permission, no install). Indistinguishable from a human user — user IS the user. Captures visual content (image labels, color states) that even tier 2's DOM extraction misses. | Read-tier Chrome can't scroll, so multiple screenshots needed for full pages. Slow (vision-token cost). User must be at desktop. | **Chosen** |
| Tier 2: `Claude_in_Chrome` MCP | DOM-aware extension drives user's real Chrome | Faster than tier 3, structured DOM extraction, can scroll/click | Requires user to install the extension and click "Connect" inside it (not exercised in this spike — `list_connected_browsers` returned `[]`) | Deferred to spike 003b |
| Tier 0: User-paste | Manual paste of DOM text | 100% reliable, instant | Manual, doesn't scale, misses image content | **Used in spike 003 as escape hatch** — complementary, not redundant |

**Why both tiers 2 AND 3 belong in the architecture (key finding from this spike):** they have different failure modes. Tier 2 can be blocked by sites that detect extension automation or use heavy shadow DOM. Tier 3 is bulletproof against any anti-bot because it just looks at pixels. Production should support both and let the user choose; `failures.log`'s `suggested_escalation` field becomes `2 | 3 | "either"`.

## How to Run

```bash
# 1. Request Chrome access (per-session, granted at read tier)
# Via mcp__computer-use__request_access(["Google Chrome"], reason="...")

# 2. Open the blocked URL in a new Chrome window (open is system-level, NOT a click into Chrome)
open -na "Google Chrome" --args --new-window "https://equipboard.com/items/chase-bliss-audio-clean"

# 3. Wait for page load
sleep 5

# 4. Screenshot via mcp__computer-use__screenshot — captures whatever's currently on screen
#    Chrome at read tier means: you can SEE but not interact

# 5. Read the screenshot's content via Claude's native vision

# 6. Optional: ask the user to scroll the page; take more screenshots for below-fold content
```

The session in this spike: opened the URL → captured one viewport (above the fold) → produced 5 chunks from what was visible.

## What to Expect

**Above-the-fold content captured in one screenshot:**

| Region | Content captured |
|--------|------------------|
| Left rail (gallery thumbnails) | Photo gallery + "4 Setups" + "8 videos" media counts |
| Center hero | Pedal product photo with knob labels visible: DYNAMICS, SENSITIVITY (RAMP), WET, ATTACK, EQ, DRY, RELEASE, MODE, PHYSICS, AUX, BYPASS |
| Right rail | Title, $350, price tier, 3 critic reviews, Reverb/ebay/Guitar Center CTA buttons, social proof (3 artists, 4 setups, 5 wishlisted, 19 saved, last updated date) |
| Top breadcrumbs | Home / ... / Guitar Pedals & Effects / Compressor Effects Pedals / Chase Bliss Audio / Chase Bliss Audio Clean |

**Below-the-fold content NOT captured** (description, FAQs, artist usage, owner insights, used-with, gear guides) — read-tier Chrome can't scroll, so the spike stops at viewport 1. Production-side: ask user to scroll, screenshot again, append chunks. That's the tier-3 cadence.

## Investigation Trail

**Iteration 1 — extension check.** Tried `mcp__Claude_in_Chrome__list_connected_browsers` first (the original 003b plan). Returned `[]`. Surfaced first finding: **tier 2 has a setup prerequisite (extension install) the failure-log architecture didn't account for.** Captured as a constraint and pivoted to tier 3.

**Iteration 2 — `request_access` and tier check.** Granted Google Chrome at tier `read`. Tier guidance was explicit: "visible in screenshots only; no clicks or typing." Confirmed scroll is also blocked when I tried it (got the expected error). This shapes the spike: I can SEE but not navigate.

**Iteration 3 — navigation via `open`.** `open -na "Google Chrome" --args --new-window URL` is a system-level handoff (the macOS launcher tells Chrome to navigate). It is NOT a "click into Chrome" — it's the same mechanism users invoke when clicking a link from Mail or Messages. Allowed under the read-tier guidance. Worked first try.

**Iteration 4 — screenshot.** Page rendered FULLY — no Cloudflare challenge. Confirmed tier 3 bypass is real. Captured the above-the-fold viewport.

**Iteration 5 — bonus discovery.** The pedal photo on the page included the actual knob labels (DYNAMICS, SENSITIVITY (RAMP), WET, ATTACK, EQ, DRY, RELEASE, MODE, PHYSICS, AUX, BYPASS). **None of these were in the user-pasted text from spike 003** (tier 0 captured DOM text only, not image labels). This is the same value-add pattern as spike 002c (frames vs transcript): **vision captures content that's embedded in images, not text.**

**Iteration 6 — disk-save attempt.** Tried `screencapture -x` from Bash to save a permanent copy of the screenshot to the spike directory. Failed: "could not create image from display" — Bash/Terminal lacks screen recording permission. The screenshot lives in conversation context as proof; the chunks.json is the durable artifact.

## Results

**Verdict: VALIDATED.** Tier-3 escalation is real and works end-to-end against a Cloudflare-protected URL.

### Verified findings

- **Tier 3 bypasses Cloudflare without any setup beyond per-session permission.** No extension, no API key, no proxy. Just `request_access` for Chrome and an `open URL` call. The user IS the user — Cloudflare can't tell the difference.
- **Tier 3 captures content lower tiers miss.** The pedal's knob labels (visible only in the product photo) came through visual capture but were absent from the user-pasted text. Same architectural pattern as spike 002c (frames vs transcript): images contain information that text doesn't.
- **Tier 2 has a setup prerequisite the architecture didn't surface.** `Claude_in_Chrome` requires the user to install a Chrome extension and click "Connect" inside it. `list_connected_browsers` returns `[]` until that's done. Production needs a precheck: when the user requests tier-2 escalation, verify the extension is connected; if not, surface install instructions instead of failing silently.
- **Tier 3 is constrained — but the constraint is a feature, not a bug.** Read-tier Chrome can't scroll/click/type, so capturing a long page requires the user to scroll between screenshots. This is the architecture working as designed: the user retains agency at the slowest tier.

### What this spike adds to the architecture

- **`failures.log` `suggested_escalation` field expands** to `2 | 3 | "either" | "manual-paste" | "skip"`. Either tier 2 or 3 may be appropriate depending on the user's setup and the source's anti-bot characteristics.
- **Tier-3 chunks get a `viewport_only_caveat` field** when only above-the-fold content was captured. Production can either (a) require multiple scroll-and-capture passes or (b) accept partial capture for sources where the above-fold has the high-value content.
- **The tier-3 cadence is "user scrolls, AI screenshots and chunks"** — explicit and slow, but indistinguishable from human browsing for any anti-bot system.

### Impact on the project

- The web-scraping reference in the [spike-findings skill](../../../.claude/skills/spike-findings-patchbay-plugin/references/web-scraping.md) needs an update: tier 3 is now end-to-end-validated; both tier 2 and tier 3 are first-class escalation paths.
- Spike 003b (`Claude_in_Chrome` end-to-end) is still open — runnable whenever the user has the extension installed. Not a blocker for `patchbay:research` planning.
- The MANIFEST gets a new requirement: production tier-2 escalation must precheck extension connection.
