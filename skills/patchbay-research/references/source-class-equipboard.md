# Source Class: Equipboard

The **meta-aggregator** source class for `/patchbay:research` — and the single highest-leverage external source for the knowledge graph. Equipboard item pages carry verbatim text from YouTube reviewer videos that Equipboard's editors have already scraped, so a successful Equipboard ingest delivers reviewer commentary without running the YouTube source class for sources EB has already covered.

This source class is **expected to fail at tier 1** (Cloudflare 403 + JS challenge) on most runs. Its `parse_to_chunks` function is the load-bearing part — it operates against any successfully-fetched DOM regardless of which tier supplied it.

## URL pattern

`match_url` returns True iff ALL of the following hold:

| Component | Rule |
|---|---|
| Scheme | `http` or `https` |
| Host (`netloc`) | EXACT match in `{ equipboard.com, www.equipboard.com }` — never substring containment |
| Path | matches `/items/<slug>(/.*)?` |

Inspection is via `urllib.parse.urlparse`, never substring matching on the raw URL. This is the T-03-14 mitigation — `https://equipboard.com.attacker.io/items/x` is rejected because its host is not in the allow-set.

```python
match_url("https://equipboard.com/items/chase-bliss-clean")              # True
match_url("https://www.equipboard.com/items/chase-bliss-clean")           # True
match_url("https://equipboard.com/artists/foo")                           # False (path)
match_url("https://equipboard.com.attacker.io/items/x")                   # False (host)
match_url("javascript:alert(1)")                                          # False (scheme)
```

## Cloudflare expectation

Equipboard is consistently behind Cloudflare. Tier-1 fetches return HTTP 403 with a body containing `"Just a moment..."` and `"Checking your browser"` regardless of User-Agent (spike 003 verified that both the default `python-requests` UA and a Chrome desktop UA return 403). The challenge is JavaScript-based, so tier-1 has no realistic bypass.

Plan 01's shared `classify_reason` maps this outcome to `("cloudflare-block", 2)` — the suggested escalation is tier 2 (Claude_in_Chrome), validated end-to-end in spike 003b.

| Status / signal | `classify_reason` output | What happens |
|---|---|---|
| 200 + valid HTML | (n/a — chunks written via `write_chunks`) | Tier-1 succeeded (rare). |
| 403 + `Just a moment...` body | `("cloudflare-block", 2)` | Append failure entry; surface to user via `--review-failures`. Default suggested action: tier 2. |
| 403 + CAPTCHA marker | `("bot-detected", 3)` | Same flow; default action tier 3. |
| 429 | `("rate-limited", "skip")` | Rare — Cloudflare rate-limits before reaching this. |
| 5xx | `("other", "either")` | Backend hiccup. |

The `equipboard.fetch_tier1` callable does NOT do anything Equipboard-specific at the network layer — it forwards the shared tier-1 result unchanged. Classification is centralized in `scripts/log_failure.classify_reason`.

## Chunk-type mapping

`parse_to_chunks` operates against the body of any successful fetch (tier 1, 2, or 3). Phase 3 Plan 05's `--review-failures` flow passes tier-2/3 captures to this same parser with `fetch_result["tier"]` set to the actual tier.

| DOM landmark | Chunk type | Notes |
|---|---|---|
| Page description (`section.item-description` or first `<p>` under `<main>`) | `text` | One per page. Content is a markdown string. |
| Each artist-usage block (`div.artist-usage`, or section whose heading mentions "Artists" / "Used by") | `artist_usage` | One per artist. `verbatim_quote` when a single text node ≥ 80 chars is present, `summary` otherwise. `alternatives_recommended` lifted from an "also recommends" list. |
| "Used With" rollup (`section.used-with` or section whose heading starts with "Used with") | `cross_ref` | `relation: used_with`. One chunk total. |
| "Similar in <category>" list (`section.similar-in-category` or section whose heading starts with "Similar in") | `cross_ref` | `relation: similar_in_category`. One chunk total. |
| YouTube URLs found inside any artist-usage block | `external_resource` | One per unique YouTube URL. `citing_chunk_ids` lists the enclosing `artist_usage` chunk's id; `creator` is set to that artist's name. |

Every chunk carries:

- `source: "equipboard"`
- `tier_used: fetch_result.get("tier", 1)` — defaults to 1; tier-2/3 callers set the actual tier
- `provenance.url`, `provenance.section` (DOM section anchor, e.g., `#artist-rhett-shull` / `#used-with` / `#similar-in-category` / `description`), `provenance.scraped_at` (from `gear_ctx`)

`verification_type` on `artist_usage` is one of `youtube` / `interview` / `photo` / `unknown`, derived from in-block evidence (presence of a YouTube link → `youtube`; the word "interview" → `interview`; "photo" / "Instagram" / "pedalboard photo" → `photo`; else `unknown`).

## Chunk ID format

`eb-<slug>-<suffix>` where `<slug>` is the path segment after `/items/`.

| Suffix | Example | Notes |
|---|---|---|
| `c01` | `eb-chase-bliss-clean-c01` | Page description. |
| `artist-<artist-slug>` | `eb-chase-bliss-clean-artist-rhett-shull` | Per artist block. The `artist-slug` is a lower-snake-slug of the artist name (e.g., `Rhett Shull` → `rhett-shull`). |
| `used-with` | `eb-chase-bliss-clean-used-with` | The Used With cross_ref. |
| `similar` | `eb-chase-bliss-clean-similar` | The Similar-in-category cross_ref. |
| `ext-<NN>` | `eb-chase-bliss-clean-ext-01` | The Nth external_resource (YouTube URL inside an artist block). Counter is per-page, zero-padded. |

**Stability rule:** the slug is derived from the URL path; if the Equipboard editor changes the slug, the IDs change. Within a single page, the artist slug stays stable because it's derived from the artist's displayed name.

## Why Equipboard is the meta-aggregator

Equipboard's `artist_usage` blocks **already include verbatim text from YouTube reviewer videos** that EB editors have scraped — `Rhett Shull's "How Did They Even Think Of This?"` video's full transcript becomes embedded text on the Chase Bliss Clean page, attributed to Rhett. This means ingesting Equipboard delivers reviewer commentary without running the YouTube source class (Plan 04) for sources EB has already covered.

Practical consequence: when the future conversational AI surfaces "Rhett Shull thinks the Wet/Dry split changes everything about how you track guitars", the citation anchor is the Equipboard `artist_usage` chunk's `provenance.url` — but the data substrate is Rhett's video. The cross-source-match-candidates pass (Plan 01's `write_chunks`) catches the corroboration when the YouTube source class later ingests Rhett's video directly: `cross_source_match_candidates` on both chunks will list the gear name in common.

Cited in spike-findings: `.claude/skills/spike-findings-patchbay-plugin/references/web-scraping.md` § "Equipboard-specific gold" and § "Knowledge-graph chunk types (the high-leverage ones)".

## Example chunks

### `artist_usage` (with verbatim quote + YouTube citation)

```json
{
  "id": "eb-chase-bliss-clean-artist-rhett-shull",
  "type": "artist_usage",
  "source": "equipboard",
  "content": {
    "artist": "Rhett Shull",
    "artist_roles": ["Guitarist", "Music Producer"],
    "associated_act": "",
    "verification_type": "youtube",
    "verification_note": "Video review: How Did They Even Think Of This? Chase Bliss Clean",
    "verbatim_quote": "This is hands-down the most musical compressor I've ever put on my pedalboard — it's like a studio-grade 1176 you can squish in front of your amp. I had no idea a parallel compression pedal could sound this open. The Wet/Dry split changes everything about how I track guitars now, and the Attack control gives you proper transient shaping. Genuinely don't know how they thought of this.",
    "summary": "Roles: Guitarist, Music Producer Video review: How Did They Even Think Of This? Chase Bliss Clean Also recommends: UA 1176, JHS Pulp N Peel",
    "alternatives_recommended": ["UA 1176", "JHS Pulp N Peel"]
  },
  "tier_used": 2,
  "provenance": {
    "url": "https://equipboard.com/items/chase-bliss-clean",
    "section": "#artist-rhett-shull",
    "scraped_at": "2026-05-16T02:30:00Z"
  }
}
```

### `cross_ref` (used_with)

```json
{
  "id": "eb-chase-bliss-clean-used-with",
  "type": "cross_ref",
  "source": "equipboard",
  "content": {
    "from_gear": "Chase Bliss Audio Clean",
    "relation": "used_with",
    "to_gear": [
      "Strymon Timeline",
      "JHS Morning Glory",
      "Origin Effects Cali76 Compact Deluxe"
    ],
    "weight": null
  },
  "tier_used": 2,
  "provenance": {
    "url": "https://equipboard.com/items/chase-bliss-clean",
    "section": "#used-with",
    "scraped_at": "2026-05-16T02:30:00Z"
  }
}
```

### `cross_ref` (similar_in_category)

```json
{
  "id": "eb-chase-bliss-clean-similar",
  "type": "cross_ref",
  "source": "equipboard",
  "content": {
    "from_gear": "Chase Bliss Audio Clean",
    "relation": "similar_in_category",
    "to_gear": [
      "Origin Effects Cali76 Compact Deluxe",
      "Empress Compressor",
      "JHS Pulp N Peel"
    ],
    "weight": null
  },
  "tier_used": 2,
  "provenance": {
    "url": "https://equipboard.com/items/chase-bliss-clean",
    "section": "#similar-in-category",
    "scraped_at": "2026-05-16T02:30:00Z"
  }
}
```

### `external_resource` (YouTube reviewer URL inside an artist block)

```json
{
  "id": "eb-chase-bliss-clean-ext-01",
  "type": "external_resource",
  "source": "equipboard",
  "content": {
    "resource_type": "youtube",
    "creator": "Rhett Shull",
    "title": "",
    "url": "https://www.youtube.com/watch?v=ABC123XYZ",
    "updated": null,
    "relevance": "artist_usage_citation",
    "citing_chunk_ids": ["eb-chase-bliss-clean-artist-rhett-shull"]
  },
  "tier_used": 2,
  "provenance": {
    "url": "https://equipboard.com/items/chase-bliss-clean",
    "section": "#artist-rhett-shull",
    "scraped_at": "2026-05-16T02:30:00Z"
  }
}
```

## Live-DOM compatibility

The live 2026 equipboard.com pages do NOT use the semantic class names the
synthetic fixture (`scripts/fixtures/equipboard_sample.html`) was built
against — they ship Tailwind utility classes that the Equipboard team
rotates on a regular cadence. The parser handles this with a two-layer
strategy.

**Primary: JSON-LD `@graph` parsing.** Every item page ships exactly one
`<script type="application/ld+json">` block whose `@graph` includes:

- a `Product` entity with `description` (used for the `text` chunk),
- an `ItemList` entity whose `@id` ends in `#artistUsage` and whose
  `itemListElement` is a list of `{"item": {"@type": "Person", "name",
  "description", "subjectOf": {"name", "url"}}}`. This is the canonical
  artist list — `_build_artist_chunks_from_jsonld` emits one
  `artist_usage` chunk per entry,
- plus an `ItemList #ownerInsights`, a `FAQPage`, a `BreadcrumbList`, a
  `WebPage`, and an `Organization` (not currently consumed but reserved
  for future enrichment).

`subjectOf.url` is the YouTube backlink — when it points at
`youtube.com` / `youtu.be` / `m.youtube.com` (re-validated via
`urlparse`), an `external_resource` chunk is emitted with
`citing_chunk_ids` referencing the enclosing artist's `artist_usage`
chunk. Non-YouTube `subjectOf.url`s (Instagram, Reddit, talkbass,
reverb.com, etc.) are captured as `verification_note` strings on the
artist chunk.

> **`json.loads` strict mode.** Equipboard embeds literal newlines inside
> `description` string values (the descriptions are multi-line prose).
> RFC 8259 forbids unescaped control characters in string values, so
> `json.loads(raw)` raises. The parser calls `json.loads(raw, strict=False)`
> — strict-False tolerates raw `\n` / `\t` inside strings. Without that
> flag the entire JSON-LD blob is silently skipped and the parser falls
> all the way through to the legacy synthetic-DOM path.

**Fallback: live-DOM extraction for `used_with` / `similar`.** The JSON-LD
does NOT include the Used-With rollup or the curated Similar list, so
these are extracted from the DOM:

- `_find_used_with_from_dom` reads `#eb-item-page-used-with-container`
  (or `#usedWith`) and lifts gear names from `<a href="/items/...">`
  anchors.
- `_find_similar_from_dom` reads the curated container
  `.eb-item-page-curated-similar-items-container` (or `#similarProducts`
  as a deeper fallback). Anchor `title=` is preferred; visible text is
  the fallback.

**Legacy synthetic-DOM path.** When no JSON-LD `#artistUsage` ItemList
is present (e.g., the original `equipboard_sample.html` fixture used by
tests 1–11), `_parse_artists_from_dom` runs against the
`.artist-usage` / `.artist-name` / `.verbatim-quote` class names. This
path stays in the module purely to keep the original 11 acceptance tests
green; new fixtures should mirror live HTML, not synthetic DOM.

**Section-heading guard.** `_is_plausible_artist_name` rejects strings
that contain `"artist usage"`, `"album usage"`, `"load more"`, `"see
more"`, or `"show more"` (case-insensitive) — this fixes the headline
regression from the 2026-05-17 production smoke where the parser
captured "Album Usage" as an artist name when the live DOM selectors
drifted out from under the heading-fallback code path.

**Regression fixture.** `scripts/fixtures/equipboard_live_2026.html` is
the verbatim HTML captured from `equipboard.com/items/boss-bf-3-flanger-pedal`
during the 2026-05-17 production smoke. Test cases:
`test_parse_live_2026_emits_at_least_10_named_artist_chunks`,
`test_parse_live_2026_emits_used_with_cross_ref`,
`test_parse_live_2026_emits_similar_in_category_cross_ref`,
`test_parse_live_2026_emits_external_resource_for_subjectof_youtube`,
`test_parse_live_2026_tier_used_is_two_when_fetched_via_tier2`. When
Equipboard rotates its DOM again, replace the fixture with a fresh
capture from the same URL and either update the JSON-LD selectors or
the live-DOM fallback selectors (NOT both unless both layers drifted).

## Tier-2 fetch contract: raw HTML, not plaintext

`scripts/tier2_chrome.fetch_tier2` returns the raw HTML body
(`document.documentElement.outerHTML`) via the MCP `javascript_tool`,
NOT the plaintext from `get_page_text`. The pre-fix code path used
`get_page_text`, which silently strips the JSON-LD `<script>` blocks
along with every `class=` / `id=` attribute the live-DOM fallback
relies on — meaning a production tier-2 fetch would have returned
zero `artist_usage` chunks regardless of how good the selectors were.

The parser does not need to care about which fetch tier produced the
body: every successful fetch (`tier_used` 0 paste / 1 static / 2 chrome
/ 3 vision-screenshot) must deliver raw HTML. The
`test_fetch_tier2_body_is_raw_html_not_plaintext` test pins this
contract.

## Cross-source corroboration cap

A single chunk's `cross_source_match_candidates` is capped at
`MAX_NAME_CANDIDATES = 25` (defined in `scripts/write_chunk.py`). The
2026-05-17 smoke produced a chunk whose match cluster blew out to 199
entries — every comma-separated TitleCase token in a plaintext-extracted
megablob got promoted to a candidate. The cap is defense-in-depth: the
upstream parser is now well-behaved, but a future regression in name
extraction should not be allowed to turn the corroboration field into a
denial-of-readability signal. Test:
`test_cross_source_matches_caps_runaway_titlecase_blob`.

## Security mitigations (T-03 register)

| Threat ID | Mitigation site |
|---|---|
| T-03-13: scheme abuse | `match_url` rejects non-http(s) schemes before the host check. |
| T-03-14: substring-host confusion | `match_url` uses exact set-membership over `ALLOWED_HOSTS`. |
| T-03-15: XXE in HTML payload | BeautifulSoup is invoked with `html.parser` (stdlib) — no external XML processor. |
| T-03-16: injection via free-form artist/gear text | Extracted strings are treated as opaque data; chunks are JSON-encoded via Plan 01's `write_chunks` (real `json.dumps`, never raw concat). |
| T-03-17: non-http URLs embedded in artist blocks | YouTube URL extractor re-parses each candidate via `urlparse` and discards non-http(s) schemes. |

## Origin

Synthesized from spike findings — see `.claude/skills/spike-findings-patchbay-plugin/references/web-scraping.md` § "Equipboard-specific gold" and § "Knowledge-graph chunk types (the high-leverage ones)" and § "Tier-2 escalation (Claude_in_Chrome) — VALIDATED in spike 003b". Spike 003 confirmed the Cloudflare-block expectation; spike 003b validated tier-2 DOM extraction end-to-end against the Chase Bliss Clean Equipboard page; the chunk shapes here are the locked Phase 2 / Phase 3 schema documented at `skills/patchbay-ingest/references/chunk-schema.md`.

## UI layer notes

(Required per user memory rule — parallel UI notes accompany every patchbay spec.)

- **Per-artist deep links.** Each `artist_usage` chunk's `provenance.deep_link` (when added — current MVP carries `provenance.section` only) is intended to be `<page-url>#artist-<artist-slug>`, so the future hover-citation UI can fragment-jump straight into that artist's section of the Equipboard page. Today, `provenance.section` carries the `#artist-<slug>` anchor; a future UI helper can compose `provenance.url + provenance.section` to produce the deep link without a schema change.
- **`artist_usage` rendering.** Render each artist as a card with: artist name (heading) + role badge(s) (one badge per entry in `artist_roles`) + `verbatim_quote` displayed as a pull-quote with attribution, if non-null; `summary` rendered as supporting prose. When `verification_type == "youtube"`, surface the linked YouTube video (the corresponding `external_resource` chunk whose `citing_chunk_ids` includes this artist_usage chunk's id) as a "see the video" affordance directly under the quote.
- **Reviewer attribution surfacing.** When an `artist_usage` chunk contains a verbatim YouTube reviewer quote, the future UI must surface the reviewer (Rhett Shull, in the example) as the citation anchor — NOT the Equipboard editor or the Equipboard page itself. The hover-citation should read "Rhett Shull, via Equipboard's artist-usage entry" with the linked YouTube video as the primary source and the Equipboard page as the secondary/aggregator source. This is the Equipboard-specific two-link citation pattern (mirrors the Reddit-thread-with-external-link pattern from Plan 02, but with the meta-aggregator role reversed).
- **`cross_ref` chunks power the gear graph.** `used_with` cross_refs render as a sidebar on the gear card ("Often used with: Strymon Timeline · JHS Morning Glory · Origin Cali76"), each entry hover-citable back to this Equipboard chunk. `similar_in_category` cross_refs power a "similar gear" affordance that surfaces alternatives the user does not own (cross-referenced against the user's `<gear_root>`). Edge weights (`content.weight`) are null today; when Phase 4 cross-source aggregation lands, the UI can render thicker lines for highly-corroborated edges.
- **Tier-of-origin badge.** Because Equipboard typically arrives via tier 2 or tier 3 (Cloudflare-blocked at tier 1), every Equipboard chunk should render a small tier badge — tier-2 means "captured from real-browser DOM, structured", tier-3 means "captured from screenshot vision, may include image-embedded text". This helps the user calibrate trust on the rare tier-3 chunks where vision extraction may have misread small printed labels.
- **`external_resource` cross-linking.** The `external_resource` chunks emitted here have `citing_chunk_ids` pointing back at the originating `artist_usage` chunk. When Plan 04's YouTube source class later enriches these (filling `title`, `updated`, `creator` where blank) via Plan 01's `update_chunk_field`, the UI surfaces a unified "Rhett Shull on YouTube" card with two-link citation: video as primary, Equipboard mention as discovery breadcrumb.
