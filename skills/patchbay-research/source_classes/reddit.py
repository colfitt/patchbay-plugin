"""Reddit source class — the cheap path for `/patchbay:research`.

Reddit threads have a universally reachable `.json` endpoint that returns the
full post + comments tree with no auth or anti-bot challenge. This source
class:

    1. `match_url(url)` — exact-host match on `reddit.com` / `www.reddit.com`
       / `old.reddit.com` with a `/r/<sub>/comments/<id>` path.
    2. `fetch_tier1(url)` — rewrites the URL to its `.json` form (canonical
       path-suffix, NOT `/.json`) and delegates to the shared tier-1 fetch
       in `scripts/fetch_tier1.py`.
    3. `parse_to_chunks(result, gear_ctx)` — emits three chunk types:
         - one `text` (or `review_section` if selftext > 2000 chars) for the OP
         - one `comment_aggregate` for the top-N=10 comments by ups
         - one `external_resource` per unique http(s) URL found in OP or
           comment bodies

SECURITY mitigations (from the plan's threat register):
  - T-03-07: non-http(s) schemes are rejected by `match_url` BEFORE host check.
  - T-03-08: host check uses exact set membership, never substring containment.
  - T-03-09: permalink reconstruction validates the path begins with `/r/`
    before concatenating with `https://reddit.com`; falls back to the input
    URL otherwise.
  - T-03-10: external URL extraction validates each candidate's scheme is
    http/https via `urlparse` and discards everything else.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Optional
from urllib.parse import urlparse

# The shared tier-1 fetcher (SSRF guard, 15s timeout). Imported under an
# alias so tests can monkeypatch it without colliding with this module's
# own `fetch_tier1`.
try:
    # Preferred import path when `skills/patchbay-research` is on sys.path.
    from scripts.fetch_tier1 import fetch_tier1 as _shared_fetch_tier1  # type: ignore
except ImportError:  # pragma: no cover — fallback for unusual import layouts
    from ..scripts.fetch_tier1 import fetch_tier1 as _shared_fetch_tier1  # type: ignore


# ---------------------------------------------------------------------------
# URL matching
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = frozenset({"reddit.com", "www.reddit.com", "old.reddit.com"})
ALLOWED_SCHEMES = frozenset({"http", "https"})

# Path must look like /r/<sub>/comments/<id>(/<slug>)?(/)?
_COMMENT_PATH_RE = re.compile(r"^/r/[^/]+/comments/[^/]+(?:/[^/]*)?/?$")


def match_url(url: str) -> bool:
    """Return True iff `url` is a Reddit comment-thread URL.

    Scheme MUST be http or https (T-03-07). Host MUST be an exact match
    against `ALLOWED_HOSTS` — never substring containment (T-03-08). Path
    MUST match `/r/<sub>/comments/<id>(/<slug>)?`.

    All decisions go through `urllib.parse.urlparse` — no substring matching
    on the raw URL.
    """
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return False
    host = (parsed.netloc or "").lower()
    if host not in ALLOWED_HOSTS:
        return False
    if not _COMMENT_PATH_RE.match(parsed.path or ""):
        return False
    return True


# ---------------------------------------------------------------------------
# Tier-1 fetch (with .json rewrite)
# ---------------------------------------------------------------------------


def _to_json_url(url: str) -> str:
    """Rewrite a Reddit comment URL into its `.json` form.

    Strips a trailing slash, then appends `.json` to the path. Query string
    and fragment are preserved on the rewritten URL.

    Examples:
        https://reddit.com/r/x/comments/abc/slug/    -> https://reddit.com/r/x/comments/abc/slug.json
        https://reddit.com/r/x/comments/abc          -> https://reddit.com/r/x/comments/abc.json
        https://reddit.com/r/x/comments/abc?foo=bar  -> https://reddit.com/r/x/comments/abc.json?foo=bar
    """
    parsed = urlparse(url)
    path = parsed.path or ""
    # Strip trailing slash so we get `.../slug.json`, NEVER `.../slug/.json`.
    if path.endswith("/"):
        path = path[:-1]
    if not path.endswith(".json"):
        path = path + ".json"
    rebuilt = f"{parsed.scheme}://{parsed.netloc}{path}"
    if parsed.query:
        rebuilt += f"?{parsed.query}"
    if parsed.fragment:
        rebuilt += f"#{parsed.fragment}"
    return rebuilt


def fetch_tier1(url: str) -> dict:
    """Fetch the Reddit thread JSON via the cheap `.json` path.

    Returns a dict shaped like the shared tier-1 result plus a parsed `json`
    field (None if the body wasn't valid JSON) and `url_attempted` so callers
    can confirm the URL the network call actually hit.
    """
    rewritten = _to_json_url(url)
    result = _shared_fetch_tier1(rewritten)

    parsed_json: Optional[Any] = None
    body = result.get("body")
    if isinstance(body, str) and body:
        try:
            parsed_json = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            parsed_json = None

    return {
        "status": result.get("status", 0),
        "body": body,
        "json": parsed_json,
        "url_attempted": rewritten,
        "headers": result.get("headers", {}),
        "elapsed_ms": result.get("elapsed_ms", 0),
        "exc": result.get("exc"),
    }


# ---------------------------------------------------------------------------
# parse_to_chunks
# ---------------------------------------------------------------------------

TOP_N_COMMENTS = 10
SNIPPET_CHARS = 240
LONG_FORM_THRESHOLD = 2000
URL_RE = re.compile(r'https?://[^\s<>"\\)]+')


def _reconstruct_permalink(op_data: dict, fallback_url: str) -> str:
    """Build the canonical `https://reddit.com<permalink>` URL.

    Validates that `permalink` starts with `/r/` BEFORE concatenation
    (T-03-09). Falls back to the input URL if the permalink looks tampered.
    """
    permalink = op_data.get("permalink")
    if isinstance(permalink, str) and permalink.startswith("/r/"):
        return "https://reddit.com" + permalink
    return fallback_url


def _classify_url(url: str) -> Optional[str]:
    """Return `"youtube"` / `"article"` / None.

    `None` means the URL failed the scheme-validity check (T-03-10) and
    should be dropped entirely.
    """
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return None
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return None
    host = (parsed.hostname or "").lower()
    if "youtube.com" in host or host == "youtu.be" or host.endswith(".youtu.be"):
        return "youtube"
    return "article"


def _extract_urls_in_order(text: str) -> list[str]:
    """Return URLs found in `text`, in first-seen order, deduped."""
    if not isinstance(text, str):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for match in URL_RE.findall(text):
        if match not in seen:
            seen.add(match)
            out.append(match)
    return out


def parse_to_chunks(fetch_result: dict, gear_ctx: dict) -> list[dict]:
    """Convert a Reddit `.json` response into schema-conformant chunks.

    Emits, in order:
      1. ONE chunk for the OP body — `text` if `selftext` <= 2000 chars,
         else `review_section`.
      2. ONE `comment_aggregate` chunk with the top 10 comments by `ups`.
      3. ONE `external_resource` chunk per unique http(s) URL found in the
         OP body or any of the top-10 comments' bodies.

    Every chunk carries `source: "reddit"`, `tier_used: 1`, and a
    `provenance` block with `url`, `deep_link`, `scraped_at`.
    """
    payload = fetch_result.get("json")
    if not isinstance(payload, list) or len(payload) < 2:
        return []

    # listing0 = post, listing1 = comments
    op_children = (payload[0] or {}).get("data", {}).get("children") or []
    if not op_children:
        return []
    op_data = (op_children[0] or {}).get("data") or {}
    post_id = op_data.get("id")
    if not isinstance(post_id, str) or not post_id:
        return []

    scraped_at = gear_ctx.get("scraped_at", "")
    permalink_url = _reconstruct_permalink(
        op_data, fallback_url=fetch_result.get("url_attempted", "")
    )

    chunks: list[dict] = []
    counter = 1

    def _next_id() -> str:
        nonlocal counter
        cid = f"reddit-{post_id}-c{counter:02d}"
        counter += 1
        return cid

    def _provenance() -> dict:
        return {
            "url": permalink_url,
            "deep_link": permalink_url,
            "scraped_at": scraped_at,
        }

    # ----- 1. OP chunk -----
    selftext = op_data.get("selftext") or ""
    if isinstance(selftext, str):
        if len(selftext) <= LONG_FORM_THRESHOLD:
            op_chunk = {
                "id": _next_id(),
                "type": "text",
                "source": "reddit",
                "content": selftext,
                "tier_used": 1,
                "provenance": _provenance(),
            }
        else:
            title = op_data.get("title") or ""
            op_chunk = {
                "id": _next_id(),
                "type": "review_section",
                "source": "reddit",
                "content": {
                    "section_header": title,
                    "key_thesis": "",
                    "summary": selftext,
                    "framing_takeaway": "",
                    "disclosures": "",
                },
                "tier_used": 1,
                "provenance": _provenance(),
            }
        chunks.append(op_chunk)

    # ----- 2. Top comments aggregate -----
    comment_children = (payload[1] or {}).get("data", {}).get("children") or []
    comments: list[dict] = []
    for child in comment_children:
        if not isinstance(child, dict):
            continue
        if child.get("kind") != "t1":
            continue
        cdata = child.get("data") or {}
        body = cdata.get("body")
        if not isinstance(body, str):
            continue
        comments.append(
            {
                "author": cdata.get("author") or "",
                "ups": int(cdata.get("ups") or 0),
                "body": body,
            }
        )

    comments.sort(key=lambda c: c["ups"], reverse=True)
    top_comments = comments[:TOP_N_COMMENTS]

    aggregate_content = [
        {
            "author": c["author"],
            "ups": c["ups"],
            "snippet": c["body"][:SNIPPET_CHARS],
        }
        for c in top_comments
    ]
    chunks.append(
        {
            "id": _next_id(),
            "type": "comment_aggregate",
            "source": "reddit",
            "content": aggregate_content,
            "tier_used": 1,
            "provenance": _provenance(),
        }
    )

    # ----- 3. External resources -----
    url_pool: list[str] = []
    url_pool.extend(_extract_urls_in_order(selftext))
    for c in top_comments:
        url_pool.extend(_extract_urls_in_order(c["body"]))

    seen_urls: set[str] = set()
    for raw_url in url_pool:
        # Strip common trailing punctuation that can attach to URLs in prose.
        clean_url = raw_url.rstrip(".,;:!?")
        if clean_url in seen_urls:
            continue
        resource_type = _classify_url(clean_url)
        if resource_type is None:
            # Scheme guard (T-03-10) — discard non-http(s) URLs.
            continue
        seen_urls.add(clean_url)
        chunks.append(
            {
                "id": _next_id(),
                "type": "external_resource",
                "source": "reddit",
                "content": {
                    "resource_type": resource_type,
                    "creator": "",
                    "title": "",
                    "url": clean_url,
                    "updated": "",
                    "relevance": "",
                    "citing_chunk_ids": [],
                },
                "tier_used": 1,
                "provenance": _provenance(),
            }
        )

    return chunks


# ---------------------------------------------------------------------------
# Self-registration (idempotent)
# ---------------------------------------------------------------------------
# Per source-class-registry.md, each module appends itself to REGISTRY on
# import. Guarded against double-registration so importlib.reload() in tests
# does not duplicate the entry.

from . import REGISTRY as _REGISTRY  # noqa: E402

_self = sys.modules[__name__]
if _self not in _REGISTRY:
    _REGISTRY.append(_self)
