# Web Scraping (tiered, cheap-by-default + user-driven escalation)

The primary external source class for `patchbay:research`. Validated in spike 003 against Equipboard (Cloudflare-blocked → tier-1 fail → user-paste tier 0) and a Reddit "comprehensive review" thread (tier-1 success via `.json` suffix).

## Requirements

- All chunks honor the [chunk schema](./chunk-schema.md), including the **knowledge-graph types** (`artist_usage`, `cross_ref`).
- **Web scraping uses cheap-by-default + user-driven escalation, NOT auto-fallback.** Tier-1 static fetch tries first; on failure, write a structured entry to `failures.log` with suggested escalation tier; the user reviews and decides.
- **`failures.log` is append-only JSONL** with the exact schema in the spec below.
- **Reddit `.json` suffix is the cheap path** — no auth needed, returns full post + comments tree. Production should default to this for any reddit.com URL before attempting other tiers.
- **Knowledge-graph chunk types** (`artist_usage`, `cross_ref`) are higher-leverage than flat content chunks. Don't skip them.
- **Cross-source corroboration is automatic** — when multiple sources reference the same gear/artist, set `cross_source_match_candidates` on the chunk. This emerges from chunk creation, not a separate ranking pass.
- **Tier 2 AND tier 3 are both first-class escalation paths.** Tier 2 (Claude_in_Chrome extension) is faster + DOM-aware but requires user to install the extension. Tier 3 (computer-use + vision) is slower + viewport-only but needs only per-session permission and is bulletproof against anti-bot. Validated end-to-end in spike 003c.
- **Production tier-2 escalation must precheck extension connection** — `mcp__Claude_in_Chrome__list_connected_browsers` returning `[]` is a setup prerequisite, not a runtime failure. Surface install instructions, don't fail silently.

## How to Build It

### Tier model

| Tier | Tool | Behavior |
|------|------|----------|
| 1 | `requests` + `BeautifulSoup` (Python) | Cheap, instant, default attempt |
| 2 | Real browser via `Claude_in_Chrome` MCP, or `Playwright` stealth | Slower; runs JS; bypasses Cloudflare |
| 3 | Tier 2 + screenshot + Claude vision | Slowest; bulletproof against any anti-bot |
| 0 | Manual user-paste | Escape hatch — user pastes DOM text |

**Production behavior:** try tier 1 → on failure, log to `failures.log` with `suggested_escalation` → return to user. The user explicitly reviews failures and chooses which to escalate. Do **not** auto-fall-through tiers.

### Source-class-specific cheap paths

Some sources have known-cheap endpoints that bypass anti-bot for free. Detect these by URL and route directly:

| Domain | Cheap path | Escalation needed? |
|--------|------------|---------------------|
| `reddit.com/r/.../comments/...` | Append `.json` to URL → returns full thread JSON | No |
| `equipboard.com/items/...` | None (Cloudflare-blocked) | Yes — escalate to tier 2 or fall back to tier 0 |
| `sweetwater.com`, `musicradar.com` | Standard fetch usually works | Sometimes |
| `gearspace.com`, MPC-Forums, etc. | Standard fetch (older forum software) | Rarely |

### Tier-1 implementation pattern

```python
import requests, json
from bs4 import BeautifulSoup
from datetime import datetime

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def fetch_tier1(url: str) -> dict:
    # Reddit fast path
    if "reddit.com" in url and "/comments/" in url:
        if not url.endswith(".json"):
            url = url.rstrip("/") + "/.json"
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        return {"status": r.status_code, "json": r.json() if r.ok else None}

    # Generic
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    return {"status": r.status_code, "html": r.text if r.ok else None}


def log_failure(url: str, status: int, body_snippet: str) -> None:
    reason = "cloudflare-block" if "Just a moment..." in body_snippet else \
             "rate-limited" if status == 429 else \
             "404" if status == 404 else "other"
    suggested = 2 if reason == "cloudflare-block" else "manual-paste"
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "url": url,
        "tier_attempted": 1,
        "http_status": status,
        "reason": reason,
        "reason_detail": f"Server returned {status}. Body snippet: {body_snippet[:200]}",
        "suggested_escalation": suggested,
        "last_attempted": datetime.utcnow().isoformat() + "Z",
        "retry_count": 1,
    }
    with open("failures.log", "a") as f:
        f.write(json.dumps(entry) + "\n")
```

### `failures.log` schema (locked)

JSONL, append-only:

```json
{
  "timestamp": "2026-05-08T20:30:00Z",
  "url": "https://equipboard.com/items/chase-bliss-audio-clean",
  "tier_attempted": 1,
  "http_status": 403,
  "reason": "cloudflare-block",
  "reason_detail": "Server returned 403 with Cloudflare 'Just a moment...' challenge page...",
  "suggested_escalation": 2,
  "last_attempted": "2026-05-08T20:30:00Z",
  "retry_count": 1
}
```

`reason` ∈ `cloudflare-block | bot-detected | js-required | rate-limited | paywall | 404 | timeout | other`
`suggested_escalation` ∈ `2 | 3 | "manual-paste" | "skip"`

User reviews this file and decides. Production exposes a CLI or skill (`patchbay:research --review-failures`) that reads it and offers escalation per entry.

### Tier-2 escalation (Claude_in_Chrome) — VALIDATED in spike 003b

When the user opts to escalate to tier 2, the production flow drives the user's actual Chrome via the `Claude_in_Chrome` MCP server. This is **indistinguishable from a human** because it IS a human user's browser. **`get_page_text` returns the full DOM as structured plain text in one call** — the gold-standard ingest API when available.

Pattern (~10s end-to-end including page load):
1. **Precheck:** `mcp__Claude_in_Chrome__list_connected_browsers` — if `[]`, the extension isn't connected. Surface install instructions to the user, do NOT proceed silently. (Failure mode validated in spike 003c, set up validated in 003b.)
2. `mcp__Claude_in_Chrome__select_browser(deviceId=...)` — select the connected browser.
3. `mcp__Claude_in_Chrome__tabs_context_mcp(createIfEmpty=true)` — get tab context, or create a new tab.
4. **Use `browser_batch` to combine navigation + wait + (optional) screenshot** in a single call:
   ```python
   mcp__Claude_in_Chrome__browser_batch(actions=[
       {"name": "navigate", "input": {"tabId": ..., "url": "..."}},
       {"name": "computer", "input": {"tabId": ..., "action": "wait", "duration": 4}},
       {"name": "computer", "input": {"tabId": ..., "action": "screenshot"}},
   ])
   ```
5. `mcp__Claude_in_Chrome__get_page_text(tabId=...)` — pull the full DOM. **This is the actual ingest call** — returns the entire page's main-element text as structured plain text (preserves headings, lists, paragraph breaks).
6. Pipe to the chunker. Same chunk schema as every other source class.

**What tier 2 captures that lower tiers miss** (verified in spike 003b on the same Equipboard URL that all four tiers ran against):
- 6 of 8 videos that user-paste (tier 0) missed because the user only pasted the highlighted excerpt
- All 3 critic reviews with full text (tier 0 showed "0 critic reviews" — the user pasted only a sub-section)
- "Used With" category rollup
- Page metadata (added-by user, gear IQ score, add date)

**What tier 2 DOESN'T capture** (where tier 3 is still needed):
- Image-embedded text (knob labels printed on product photos, screen states in screenshots). Tier 3 vision reads these; tier 2 DOM does not.

**Recommendation:** for image-rich product pages (gear pages with control-photo hero images, video-game-style UI screenshots), do tier 2 first for structured DOM + an optional tier-3 follow-up vision pass for image-embedded content. Both bypass Cloudflare; both run on the user's real Chrome session.

### Tier-3 escalation (computer-use + Claude vision) — VALIDATED in spike 003c

When tier 2 isn't set up (no extension) OR a site breaks tier 2's DOM extraction (heavy shadow DOM, frame-busting, extension-specific blocks), tier 3 is the bulletproof fallback. Bypasses Cloudflare, anti-bot, and any DOM-level defenses because it's just looking at pixels.

Pattern:
1. `mcp__computer-use__request_access(["Google Chrome"], reason="...")` — per-session permission grant. Browsers are granted at tier `read` (no clicks/typing).
2. `open -na "Google Chrome" --args --new-window URL` — system-level navigation handoff (NOT a click into Chrome — this is the same mechanism users invoke when clicking a link from Mail). Allowed at read tier.
3. `sleep 5` (or longer for slow-loading pages)
4. `mcp__computer-use__screenshot` — captures the current viewport
5. Read the screenshot via Claude vision; produce chunks
6. **For below-fold content:** ask the user to scroll the page. Take more screenshots. Append chunks. Read-tier Chrome can't scroll programmatically — that's by design.
7. Optional: `mcp__computer-use__zoom` to inspect small UI details before chunking.

**Trade-offs:**
- ✓ Works on any site, regardless of anti-bot
- ✓ No setup beyond per-session permission grant
- ✓ Captures content embedded in images (knob labels on product photos, screen states in screenshots) — content tier-2 DOM extraction can't see
- ✗ Slower (vision-token cost per screenshot)
- ✗ Viewport-only — multi-screenshot scrolling needed for long pages
- ✗ Requires user to be at desktop with Chrome installed

**Bonus value-add:** spike 003c found that tier-3 captures the actual control labels printed on product photos (e.g., "DYNAMICS, SENSITIVITY (RAMP), WET, ATTACK, EQ, DRY, RELEASE, MODE, PHYSICS, AUX, BYPASS" on the Chase Bliss Clean) — content that tier-0 user-paste of DOM text DOES NOT include. Same architectural pattern as spike 002c (frames vs transcript): images carry information that text doesn't.

### Knowledge-graph chunk types (the high-leverage ones)

Equipboard pages produce chunks like this — DON'T skip these for "just the description text":

```json
{
  "id": "eb-cb-clean-artist-rhett",
  "type": "artist_usage",
  "source": "equipboard",
  "content": {
    "artist": "Rhett Shull",
    "artist_roles": ["Guitarist", "Music Producer"],
    "verification_type": "youtube",
    "verification_note": "Video review by Rhett Shull on his channel: 'How Did They Even Think Of This? Chase Bliss Clean'",
    "verbatim_quote": "...full text of his review pulled from the YouTube video transcript...",
    "summary": "Rhett positions Clean as an amazing compressor for sound designers and mix-engineers...",
    "alternatives_he_recommends": ["UA 1176", "JHS Pulp N Peel"]
  },
  "citation_targets": [
    { "type": "youtube", "creator": "Rhett Shull", "video_title": "..." }
  ],
  "provenance": { "url": "...", "section": "#artist-usage > Rhett Shull", "scraped_at": "...", "tier_label": "USER_PASTED" }
}
```

```json
{
  "id": "eb-cb-clean-similar-gear",
  "type": "cross_ref",
  "content": {
    "from_gear": "Chase Bliss Audio Clean",
    "relation": "similar_in_category",
    "category": "Compressor Effects Pedals",
    "to_gear_top10": [
      { "rank": 1, "gear": "Origin Effects Cali76 Compact Deluxe", "rating": 5.0 },
      ...
    ]
  },
  "cross_source_match_candidates": ["Origin Effects Cali76 Compact Deluxe", "Empress Compressor", "JHS Pulp 'N Peel"],
  "cross_source_match_note": "These three are also discussed in the Reddit review — strong cross-source corroboration."
}
```

The `cross_source_match_candidates` field is populated when ingestion notices the chunk references a name that another already-ingested source also references. Trivial implementation: maintain a per-gear "all referenced names" set across all chunks; on each new chunk, check the set.

### Equipboard-specific gold

Equipboard `artist_usage` blocks **already include verbatim text from YouTube reviews** they've scraped. This means EB ingestion delivers reviewer commentary without running the spike-002c multimodal pipeline for sources EB has already covered. EB is essentially a meta-aggregator. Treat EB chunks as containing transitive citations.

## What to Avoid

- **Don't auto-fall-through tiers.** Tier 2 and 3 are user-driven escalations, not automatic fallbacks. Cost and latency are real; the user retains agency.
- **Don't try to bypass Cloudflare in tier 1.** UA spoofing doesn't work (verified in spike 003 — both default and Chrome UAs returned 403). The challenge is JavaScript-based.
- **Don't scrape Reddit with PRAW for v1.** PRAW requires OAuth setup. The `?.json` suffix is sufficient for read-only scraping of public threads.
- **Don't over-canonicalize URLs in tier-1 logging.** Different URL forms (with/without trailing slash, with/without `?si=` tracking) might fail differently. Log them as the user gave them; deduplicate at the citation-count layer if needed.
- **Don't skip the `external_resource` chunks.** They're the foundation for the [citation-count → recommendation seed](../../planning/seeds/citation-count-recommendations.md). Track every YouTube/article URL referenced from any chunk.

## Constraints

- **Reddit `.json` payload size:** ~400KB for a long-form review thread with 64 comments. Larger threads can hit several MB.
- **Cloudflare on Equipboard, MusicRadar, Sweetwater (sometimes):** any UA returns 403 if it's a Cloudflare-protected site that's enabled bot-fight mode.
- **Visible link text vs real URL:** spike 003 didn't hit this, but article scrapers must extract `href` not display text — display text can be misleading or shortened.
- **`Claude_in_Chrome` requires the user's Chrome to be running** with the extension installed. Production should detect this and gracefully fall back to "ask user to install extension" if not present.

## Origin

Synthesized from spike 003 (VALIDATED).
Source files: `sources/003-tiered-web-ingest/README.md`, `sources/003-tiered-web-ingest/failures.log`
