# Web Scraping (tiered, cheap-by-default + user-driven escalation)

The primary external source class for `patchbay:research`. Validated in spike 003 against Equipboard (Cloudflare-blocked → tier-1 fail → user-paste tier 0) and a Reddit "comprehensive review" thread (tier-1 success via `.json` suffix).

## Requirements

- All chunks honor the [chunk schema](./chunk-schema.md), including the **knowledge-graph types** (`artist_usage`, `cross_ref`).
- **Web scraping uses cheap-by-default + user-driven escalation, NOT auto-fallback.** Tier-1 static fetch tries first; on failure, write a structured entry to `failures.log` with suggested escalation tier; the user reviews and decides.
- **`failures.log` is append-only JSONL** with the exact schema in the spec below.
- **Reddit `.json` suffix is the cheap path** — no auth needed, returns full post + comments tree. Production should default to this for any reddit.com URL before attempting other tiers.
- **Knowledge-graph chunk types** (`artist_usage`, `cross_ref`) are higher-leverage than flat content chunks. Don't skip them.
- **Cross-source corroboration is automatic** — when multiple sources reference the same gear/artist, set `cross_source_match_candidates` on the chunk. This emerges from chunk creation, not a separate ranking pass.

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

### Tier-2 escalation (Claude_in_Chrome)

When the user opts to escalate, the production flow drives the user's actual Chrome via the `Claude_in_Chrome` MCP server. This is **indistinguishable from a human** because it IS a human user's browser. No anti-bot system can reliably block it.

Pattern:
1. `tabs_context_mcp` — get current tab info
2. `navigate` to the blocked URL
3. `read_page` or `get_page_text` — extract the DOM content
4. Pipe to the same chunker that processes manual user-paste

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
