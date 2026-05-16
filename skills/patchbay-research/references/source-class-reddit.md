# Source Class: Reddit

The cheapest source class in `/patchbay:research` — Reddit threads expose a `.json` endpoint that returns the full post + comments tree with no auth, no JS, no anti-bot challenge. This source class never needs to escalate beyond tier 1.

## URL pattern

`match_url` returns True iff ALL of the following hold:

| Component | Rule |
|---|---|
| Scheme | `http` or `https` |
| Host (`netloc`) | EXACT match in `{ reddit.com, www.reddit.com, old.reddit.com }` — never substring containment |
| Path | matches `/r/<sub>/comments/<id>(/<slug>)?` |

Inspection is via `urllib.parse.urlparse`, never substring matching on the raw URL. This is the T-03-08 mitigation — `https://evil-reddit.com.attacker.io/r/x/comments/y` is rejected because its host is not in the allow-set.

```python
match_url("https://reddit.com/r/guitarpedals/comments/abc123/clean_review/")  # True
match_url("https://old.reddit.com/r/guitarpedals/comments/abc123/")           # True
match_url("https://reddit.com/r/guitarpedals/")                               # False (no /comments/)
match_url("https://evil-reddit.com.attacker.io/r/x/comments/y")               # False (host mismatch)
match_url("javascript:alert(1)")                                              # False (scheme guard)
```

## Cheap path: append `.json` to the path

Canonical rewrite: strip trailing slash from the path, then suffix with `.json`. Query string and fragment are preserved on the rewritten URL.

```
https://reddit.com/r/x/comments/abc/slug/   -> https://reddit.com/r/x/comments/abc/slug.json
https://reddit.com/r/x/comments/abc         -> https://reddit.com/r/x/comments/abc.json
https://reddit.com/r/x/comments/abc?foo=1   -> https://reddit.com/r/x/comments/abc.json?foo=1
```

The `?.json` form documented in some Reddit recipes is shell-friendly (avoids re-parsing the path) but the canonical path-suffix form is what this source class issues — it's a real URL path and survives any downstream URL-normalizer.

Payload characteristics (from spike 003):

- ~400 KB typical (one OP + few hundred comments).
- Multi-MB possible for huge AMA threads (15-second timeout from `scripts/fetch_tier1.py` is enforced regardless).
- No auth required. Standard desktop Chrome User-Agent is sufficient.
- Anti-bot: none — Reddit treats `.json` as a first-class endpoint.

## JSON → chunk mapping

The response is an array of two `Listing` objects:

| Index | Holds | Kind |
|---|---|---|
| `payload[0]` | The original post | `t3` under `data.children[0].data` |
| `payload[1]` | Top-level comments | `t1` under `data.children[*].data` |

`parse_to_chunks` emits, in order:

### 1. OP body — one chunk

- If `len(selftext) <= 2000` chars → one `text` chunk whose `content` is the verbatim selftext markdown.
- Else → one `review_section` chunk whose `content` is `{ section_header: <title>, key_thesis: "", summary: <selftext>, framing_takeaway: "", disclosures: "" }`.

The 2000-char threshold is the schema's load-bearing distinction: short conversational posts stay flat, long-form write-ups become structured review sections so Phase 4 cross-source ranking can index them as reviews. Title is lifted into `section_header` to preserve the post's framing.

### 2. Top comments — one `comment_aggregate` chunk

Top-10 `t1` comments by `ups` (descending), aggregated into a single chunk whose `content` is a list of `{ author, ups, snippet }`. `snippet` is the first 240 characters of the comment `body` — verbatim, no markdown stripping.

Only top-level comments are captured in this MVP. Nested replies are out of scope (see UI layer notes below for the threading-depth indicator we deferred).

### 3. External resources — one chunk per unique URL

Every unique http(s) URL found in OP `selftext` or in any of the top-10 comment `body` strings produces one `external_resource` chunk.

URL classification (by parsed `hostname`):

| Host | `resource_type` |
|---|---|
| `youtube.com`, `www.youtube.com`, `youtu.be`, `m.youtube.com`, … | `youtube` |
| Anything else | `article` |

`creator` and `title` are left as empty strings — Plan 04's YouTube source class enriches `external_resource` chunks of type `youtube` on demand via `update_chunk_field`.

T-03-10 mitigation: every regex-matched URL candidate is re-parsed via `urlparse` and dropped if its scheme is not http/https.

## Chunk ID format

`reddit-<post_id>-c<NN>` where `post_id` is the Reddit-assigned id from `data.id` (NOT parsed from the URL — Reddit's URL slug can be edited; the id is stable). `NN` is a zero-padded counter starting at `01`, incremented in emit order (OP → comment_aggregate → external_resources).

Examples for post id `abc123`:

```
reddit-abc123-c01   # OP body (text or review_section)
reddit-abc123-c02   # comment_aggregate
reddit-abc123-c03   # external_resource (first external URL)
reddit-abc123-c04   # external_resource (second external URL)
```

## Escalation policy

**This source class never escalates.** The `.json` endpoint is universally reachable. Failure cases:

| Status / signal | `classify_reason` output | What happens |
|---|---|---|
| 200 + valid JSON | (n/a — chunks written via `write_chunks`) | Success path. |
| 404 | `("404", "skip")` | Thread was deleted. Append failure entry; do NOT escalate. |
| 429 | `("rate-limited", "skip")` | Reddit rate-limit hit. Append failure entry; user retries later. |
| 5xx | `("other", "either")` | Reddit infrastructure hiccup. Append failure entry. |
| Network exception | classified by exception class (timeout/connect-error) | Appended to `failures.log` per Plan 01's contract. |

The `--review-failures` flow (Plan 05) surfaces these to the user but the suggested escalation for Reddit is always `skip` — there is no tier-2 or tier-3 path that adds information beyond what `.json` already returned.

## Provenance

Every Reddit chunk carries:

- `source: "reddit"`
- `tier_used: 1`
- `provenance.url` — the canonical permalink `https://reddit.com<data.permalink>` (T-03-09: validated to start with `/r/` before concatenation; falls back to the input URL otherwise).
- `provenance.deep_link` — same as `provenance.url` (no per-comment anchors in this MVP; that's a future UI affordance).
- `provenance.scraped_at` — lifted verbatim from `gear_ctx.scraped_at` (run-level timestamp from the skill).

## Example chunks

### `text` (OP body, short)

```json
{
  "id": "reddit-abc123-c01",
  "type": "text",
  "source": "reddit",
  "content": "Just spent two weeks A/B testing the Boss BF-3 against a vintage CE-2. Rhett Shull's video https://www.youtube.com/watch?v=ABC123 covers the same ground but I wanted a more practical write-up. Short version: the clean-blend mode is the killer feature.",
  "tier_used": 1,
  "provenance": {
    "url": "https://reddit.com/r/guitarpedals/comments/abc123/boss_bf3_cleanblend_review/",
    "deep_link": "https://reddit.com/r/guitarpedals/comments/abc123/boss_bf3_cleanblend_review/",
    "scraped_at": "2026-05-16T02:00:00Z"
  }
}
```

### `comment_aggregate`

```json
{
  "id": "reddit-abc123-c02",
  "type": "comment_aggregate",
  "source": "reddit",
  "content": [
    { "author": "chorusfan",  "ups": 87, "snippet": "Agreed — the clean-blend is the only reason I keep mine. Without it the BF-3 sounds like every other Boss chorus." },
    { "author": "studio_dad", "ups": 54, "snippet": "Try stacking it after a compressor. Totally different beast. Also see https://reverb.com/news/boss-bf3-deep-dive for a deeper electrical breakdown." },
    { "author": "vintage_amp","ups": 31, "snippet": "I tried this exact A/B last year. CE-2 wins for warm chorus, BF-3 wins for usability. Different tools." }
  ],
  "tier_used": 1,
  "provenance": {
    "url": "https://reddit.com/r/guitarpedals/comments/abc123/boss_bf3_cleanblend_review/",
    "deep_link": "https://reddit.com/r/guitarpedals/comments/abc123/boss_bf3_cleanblend_review/",
    "scraped_at": "2026-05-16T02:00:00Z"
  }
}
```

### `external_resource` (YouTube link extracted from OP)

```json
{
  "id": "reddit-abc123-c03",
  "type": "external_resource",
  "source": "reddit",
  "content": {
    "resource_type": "youtube",
    "creator": "",
    "title": "",
    "url": "https://www.youtube.com/watch?v=ABC123",
    "updated": "",
    "relevance": "",
    "citing_chunk_ids": []
  },
  "tier_used": 1,
  "provenance": {
    "url": "https://reddit.com/r/guitarpedals/comments/abc123/boss_bf3_cleanblend_review/",
    "deep_link": "https://reddit.com/r/guitarpedals/comments/abc123/boss_bf3_cleanblend_review/",
    "scraped_at": "2026-05-16T02:00:00Z"
  }
}
```

## Origin

Synthesized from spike findings — see `.claude/skills/spike-findings-patchbay-plugin/references/web-scraping.md` § "Source-class-specific cheap paths" and the locked tier-1 implementation pattern in the same doc. Spike 003 validated the `.json` cheap path against live Reddit threads; spike 003b confirmed the two-listing shape and `t1`/`t3` kind tags.

## UI layer notes

(Required per user memory rule — parallel UI notes accompany every patchbay spec.)

- **Permalink anchor.** `provenance.deep_link` is the canonical Reddit thread URL (`https://reddit.com/r/<sub>/comments/<id>/<slug>/`). The future hover-citation UI uses this for the "open source" affordance on any Reddit-derived chunk. There is currently NO per-comment deep-link — every chunk from a thread points back to the OP. When the UI hover surfaces a single comment from the `comment_aggregate` array, it should label the affordance "open thread" rather than "open this comment" to be honest about the granularity.
- **`comment_aggregate` display.** Render as an expandable summary card with the top-3 comments visible by default (author + ups + snippet) and a "show all 10" expander. Sort order matches storage (descending by `ups`). Each `snippet` is verbatim 240-char-truncated text — the UI must NOT re-truncate or it'll cut mid-word twice; a `…` glyph is fine as a suffix if the snippet length equals 240.
- **`external_resource` lifted from Reddit.** Chunks whose `provenance.url` host is a reddit.com variant AND whose `type` is `external_resource` get a "linked from Reddit thread" affordance hint. When the YouTube source class (Plan 04) later enriches these with `creator` + `title`, the UI surfaces both the originating thread (Reddit) and the destination video (YouTube) — a two-link citation pattern unique to this cross-source case.
- **Threading depth indicator (deferred).** This MVP captures only top-level comments. When a future enhancement adds nested replies, the UI should render a depth indicator (left-rail indent + reply-count badge) so a user reading a citation knows whether they're looking at a top-of-thread voice or a deep counter-reply. Until then, the UI may assume every captured comment is depth-0.
- **Long-form `review_section` framing.** When the OP `selftext` exceeds 2000 chars, the chunk type flips to `review_section`. The UI should render the `section_header` (the Reddit post title) prominently and the `summary` as flowing prose — the empty `key_thesis` / `framing_takeaway` / `disclosures` slots are intentional, awaiting either user annotation or a future LLM enrichment pass. Don't render empty slots as ghost-fields; suppress them in the layout when blank.
