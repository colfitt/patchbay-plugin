"""Equipboard source class — the meta-aggregator for `/patchbay:research`.

Equipboard is the single highest-leverage external source for the knowledge
graph: its item pages already include verbatim text from YouTube reviewer
videos (per spike 003 findings), so ingesting Equipboard delivers reviewer
commentary without running the YouTube source class for sources EB has
already covered.

This source class:

    1. `match_url(url)` — exact-host match on `equipboard.com` /
       `www.equipboard.com` with a `/items/<slug>` path.
    2. `fetch_tier1(url)` — delegates to the shared tier-1 fetch. Expected
       to fail with HTTP 403 + Cloudflare body on most runs; classification
       is left to the shared `classify_reason` (which maps it to
       `("cloudflare-block", 2)`).
    3. `parse_to_chunks(result, gear_ctx)` — emits, against any successfully-
       fetched DOM (tier 1, 2, or 3):
         - one `text` chunk for the page description
         - one `artist_usage` chunk per artist block (with `verbatim_quote`
           when present, `summary` otherwise, `alternatives_recommended`
           when an "also recommends" list is present)
         - one `cross_ref` chunk for the "Used With" rollup
           (`relation: used_with`)
         - one `cross_ref` chunk for the "Similar in <category>" list
           (`relation: similar_in_category`)
         - one `external_resource` chunk per YouTube URL found inside any
           artist block, with `citing_chunk_ids` referencing the enclosing
           `artist_usage` chunk.

SECURITY mitigations (from the plan's threat register):
  - T-03-13: non-http(s) schemes rejected by `match_url` BEFORE host check.
  - T-03-14: host check uses exact set membership, never substring containment.
  - T-03-15: BeautifulSoup is invoked with `html.parser` (stdlib only — no
    `lxml`). The stdlib parser does NOT resolve external entities, so XXE
    is structurally impossible regardless of input payload.
  - T-03-16: Every extracted string is opaque data — never `eval`'d, never
    inserted into shell commands. Chunk objects are written via Plan 01's
    `write_chunks` which JSON-encodes via `json.dumps`.
  - T-03-17: External URL extraction validates each candidate's scheme is
    http/https via `urlparse` and discards everything else.
"""

from __future__ import annotations

import html as _html_unescape
import json
import re
import sys
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

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

ALLOWED_HOSTS = frozenset({"equipboard.com", "www.equipboard.com"})
ALLOWED_SCHEMES = frozenset({"http", "https"})

# Path must look like /items/<slug>(/...)? — at minimum the leading /items/.
_ITEM_PATH_RE = re.compile(r"^/items/[^/]+(?:/.*)?$")


def match_url(url: str) -> bool:
    """Return True iff `url` is an Equipboard item-page URL.

    Scheme MUST be http or https (T-03-13). Host MUST be an exact match
    against `ALLOWED_HOSTS` — never substring containment (T-03-14). Path
    MUST match `/items/<slug>`.

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
    if not _ITEM_PATH_RE.match(parsed.path or ""):
        return False
    return True


# ---------------------------------------------------------------------------
# Tier-1 fetch
# ---------------------------------------------------------------------------


def fetch_tier1(url: str) -> dict:
    """Attempt a tier-1 static GET of `url` via the shared helper.

    Equipboard is expected to be Cloudflare-blocked at tier 1; this module
    does NOT do anything Equipboard-specific at the network layer. The
    shared `classify_reason` in Plan 01 will map the 403 + Cloudflare body
    to `("cloudflare-block", 2)` and the user reviews via the
    `--review-failures` flow (Plan 05).

    Returns a dict shaped like the shared tier-1 result plus `json: None`
    (Equipboard pages are HTML, not JSON) and `url_attempted` so callers
    can confirm the URL the network call actually hit.
    """
    result = _shared_fetch_tier1(url)
    return {
        "status": result.get("status", 0),
        "body": result.get("body"),
        "json": None,
        "url_attempted": url,
        "headers": result.get("headers", {}),
        "elapsed_ms": result.get("elapsed_ms", 0),
        "exc": result.get("exc"),
    }


# ---------------------------------------------------------------------------
# parse_to_chunks
# ---------------------------------------------------------------------------

_YOUTUBE_URL_RE = re.compile(
    r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s<>"\']+'
)
VERBATIM_QUOTE_MIN_CHARS = 80

# Section-heading strings that must NEVER be lifted as artist names — they
# leaked into the smoke when the live 2026 DOM-class selectors drifted and
# the parser grabbed "Album Usage" / "Artist usage" / "Load More" via the
# heading-fallback path.
_FORBIDDEN_ARTIST_NAME_SUBSTRINGS = frozenset({
    "artist usage",
    "album usage",
    "load more",
    "see more",
    "show more",
})


def _is_plausible_artist_name(name: str) -> bool:
    """Reject section-heading text masquerading as an artist name."""
    n = (name or "").strip()
    if not n or len(n) > 100:
        return False
    low = n.lower()
    return all(bad not in low for bad in _FORBIDDEN_ARTIST_NAME_SUBSTRINGS)


def _slug_from_url(url: str) -> str:
    """Extract the item slug from an Equipboard URL.

    `https://equipboard.com/items/chase-bliss-clean` -> `chase-bliss-clean`.
    Returns `"unknown"` on a malformed URL so chunk-id generation is never
    None — corrupt-but-present is better than a hard failure here because
    the parser may be invoked against tier-2/3 captures with unusual URLs.
    """
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return "unknown"
    path = parsed.path or ""
    m = re.match(r"^/items/([^/]+)", path)
    if not m:
        return "unknown"
    return m.group(1)


def _slugify(name: str) -> str:
    """Lower-snake-slug for use inside chunk IDs (e.g., artist names)."""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-") or "anon"


def _longest_text(node) -> str:
    """Return the longest single text-node string under `node`."""
    if node is None:
        return ""
    longest = ""
    for s in node.stripped_strings:
        if len(s) > len(longest):
            longest = s
    return longest


def _find_description(soup: BeautifulSoup) -> Optional[str]:
    """Find the item's main description text.

    Defensive: try `section.item-description` first, then any `<section>`
    whose class contains `description`, then a generic search for the first
    `<p>` under `<main>`. Returns None if no description is found.
    """
    sec = soup.find("section", class_="item-description")
    if sec is None:
        sec = soup.find(
            "section",
            class_=lambda c: bool(c) and "description" in " ".join(c).lower(),
        )
    if sec is not None:
        text = " ".join(sec.stripped_strings)
        if text:
            return text

    # Fallback: first <p> under <main>.
    main = soup.find("main") or soup
    p = main.find("p")
    if p is not None:
        text = " ".join(p.stripped_strings)
        if text:
            return text
    return None


def _find_artist_blocks(soup: BeautifulSoup) -> list:
    """Locate artist-usage blocks. Try a few defensive selectors."""
    blocks = soup.find_all("div", class_="artist-usage")
    if blocks:
        return blocks
    # Fallback: any section whose heading text suggests artists.
    sections = soup.find_all(["section", "div"])
    out = []
    for s in sections:
        h = s.find(["h2", "h3"])
        if h is None:
            continue
        heading = " ".join(h.stripped_strings).lower()
        if "artist" in heading or "used by" in heading:
            out.append(s)
    return out


def _find_used_with(soup: BeautifulSoup) -> list[str]:
    """Return the list of gear names from the 'Used With' rollup."""
    sec = soup.find("section", class_="used-with")
    if sec is None:
        for s in soup.find_all(["section", "div"]):
            h = s.find(["h2", "h3"])
            if h is None:
                continue
            heading = " ".join(h.stripped_strings).lower()
            if heading.startswith("used with"):
                sec = s
                break
    if sec is None:
        return []
    return [
        " ".join(li.stripped_strings)
        for li in sec.find_all("li")
        if li.find_all  # guard
    ]


def _find_similar_in_category(soup: BeautifulSoup) -> list[str]:
    """Return the list of gear names from the 'Similar in <category>' list."""
    sec = soup.find("section", class_="similar-in-category")
    if sec is None:
        for s in soup.find_all(["section", "div"]):
            h = s.find(["h2", "h3"])
            if h is None:
                continue
            heading = " ".join(h.stripped_strings).lower()
            if heading.startswith("similar in"):
                sec = s
                break
    if sec is None:
        return []
    return [
        " ".join(li.stripped_strings)
        for li in sec.find_all("li")
        if li.find_all
    ]


def _extract_youtube_urls(node) -> list[str]:
    """Return scheme-validated http(s) YouTube URLs found inside `node`.

    Regex match then `urlparse` re-validation (T-03-17 mitigation). De-duped
    in first-seen order.
    """
    text = " ".join(node.stripped_strings) if node else ""
    # Also pull from anchor href attrs, since these may not appear in the
    # text dump verbatim.
    hrefs = []
    if node is not None:
        for a in node.find_all("a"):
            href = a.get("href")
            if isinstance(href, str):
                hrefs.append(href)
    candidates = _YOUTUBE_URL_RE.findall(text) + [
        h for h in hrefs if _YOUTUBE_URL_RE.match(h or "")
    ]

    seen: set[str] = set()
    out: list[str] = []
    for raw in candidates:
        # Strip common trailing punctuation that can attach to URLs in prose.
        clean = raw.rstrip(".,;:!?")
        try:
            parsed = urlparse(clean)
        except (ValueError, TypeError):
            continue
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            continue
        host = (parsed.hostname or "").lower()
        if not (
            host == "youtube.com"
            or host == "www.youtube.com"
            or host == "m.youtube.com"
            or host == "youtu.be"
            or host.endswith(".youtube.com")
        ):
            continue
        if clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _parse_roles(block) -> list[str]:
    """Pull out role labels from an artist block, if any.

    Recognizes the `<p class="artist-roles">` convention used by Equipboard
    and falls back to any text node containing the word "Roles:".
    """
    p = block.find("p", class_="artist-roles")
    if p is None:
        for s in block.stripped_strings:
            if s.lower().startswith("roles:"):
                p_text = s
                break
        else:
            return []
        roles_str = p_text
    else:
        roles_str = " ".join(p.stripped_strings)
    # Format: "Roles: Guitarist, Music Producer"
    if ":" in roles_str:
        roles_str = roles_str.split(":", 1)[1]
    return [r.strip() for r in roles_str.split(",") if r.strip()]


def _parse_alternatives(block) -> list[str]:
    """Extract the 'also recommends' list from an artist block."""
    p = block.find("p", class_="also-recommends")
    if p is None:
        for s in block.stripped_strings:
            if "also recommend" in s.lower():
                p_text = s
                break
        else:
            return []
        alts_str = p_text
    else:
        alts_str = " ".join(p.stripped_strings)
    if ":" in alts_str:
        alts_str = alts_str.split(":", 1)[1]
    return [a.strip() for a in alts_str.split(",") if a.strip()]


def _verification_type(block, has_youtube_url: bool) -> str:
    """Classify how the artist's usage is verified, from in-block evidence."""
    if has_youtube_url:
        return "youtube"
    text = " ".join(block.stripped_strings).lower()
    if "interview" in text:
        return "interview"
    if "photo" in text or "pedalboard photo" in text or "instagram" in text:
        return "photo"
    return "unknown"


def _iter_jsonld_graph(soup: BeautifulSoup) -> Iterable[dict]:
    """Yield every dict embedded in `<script type="application/ld+json">`
    blocks, descending into `@graph` arrays. The live 2026 Equipboard page
    embeds a multi-entity `@graph` with Product, ItemList (artists, comments),
    Review, FAQPage, BreadcrumbList. Using JSON-LD as the primary source
    of truth is far more robust than scraping Tailwind class names that the
    Equipboard team rotates.
    """
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        if not raw:
            continue
        try:
            # strict=False: Equipboard embeds literal newlines inside string
            # values (e.g., artist `description` fields with hard returns).
            # RFC 8259 disallows raw control chars in strings, but `json` in
            # strict-False mode tolerates them — and that tolerance is the
            # difference between parsing the @graph and silently skipping it.
            data = json.loads(raw, strict=False)
        except (ValueError, json.JSONDecodeError):
            # Malformed JSON-LD blob — skip rather than crashing the whole
            # parse. Defensive: opaque untrusted DOM, T-03-15 etc.
            continue
        for entity in _flatten_jsonld(data):
            yield entity


def _flatten_jsonld(node: Any) -> Iterable[dict]:
    """Yield every dict found anywhere inside a JSON-LD payload, expanding
    `@graph` arrays."""
    if isinstance(node, dict):
        yield node
        graph = node.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                yield from _flatten_jsonld(child)
    elif isinstance(node, list):
        for child in node:
            yield from _flatten_jsonld(child)


def _find_artist_itemlist(soup: BeautifulSoup) -> Optional[dict]:
    """Locate the ItemList JSON-LD entity whose `@id` ends with
    `#artistUsage`. Returns the entity dict or None if absent."""
    for entity in _iter_jsonld_graph(soup):
        if not isinstance(entity, dict):
            continue
        if entity.get("@type") != "ItemList":
            continue
        atid = entity.get("@id")
        if isinstance(atid, str) and atid.endswith("#artistUsage"):
            return entity
    return None


def _find_jsonld_product_description(soup: BeautifulSoup) -> Optional[str]:
    """Pull the Product description out of JSON-LD. Cleaner than parsing
    a Tailwind-wrapped <section> for the same string."""
    for entity in _iter_jsonld_graph(soup):
        if not isinstance(entity, dict):
            continue
        if entity.get("@type") == "Product":
            desc = entity.get("description")
            if isinstance(desc, str) and desc.strip():
                return _html_unescape.unescape(desc).strip()
    return None


def _build_artist_chunks_from_jsonld(
    itemlist: dict,
    slug: str,
    tier_used: int,
    provenance_factory,
) -> tuple[list[dict], list[tuple[dict, list[str], str]]]:
    """Translate a JSON-LD `#artistUsage` ItemList into artist_usage chunks
    plus the artist_block_records list used to backlink external_resource
    chunks.

    Returns (chunks, records) where each record is
    `(jsonld_item, youtube_urls, chunk_id)`.
    """
    chunks: list[dict] = []
    records: list[tuple[dict, list[str], str]] = []
    items = itemlist.get("itemListElement") or []
    if not isinstance(items, list):
        return chunks, records

    for li in items:
        if not isinstance(li, dict):
            continue
        person = li.get("item") if isinstance(li.get("item"), dict) else None
        if person is None:
            continue
        artist_name_raw = person.get("name")
        if not isinstance(artist_name_raw, str):
            continue
        artist_name = _html_unescape.unescape(artist_name_raw).strip()
        if not _is_plausible_artist_name(artist_name):
            continue

        description_raw = person.get("description") or ""
        if isinstance(description_raw, str):
            description = _html_unescape.unescape(description_raw).strip()
        else:
            description = ""

        # YouTube URLs come out of `subjectOf.url` when present. Also accept
        # an array of subjectOf entries.
        youtube_urls: list[str] = []
        other_resource_urls: list[tuple[str, str]] = []  # (url, work_name)
        subject_of = person.get("subjectOf")
        sub_list: list[dict] = []
        if isinstance(subject_of, dict):
            sub_list = [subject_of]
        elif isinstance(subject_of, list):
            sub_list = [s for s in subject_of if isinstance(s, dict)]
        for sub in sub_list:
            sub_url = sub.get("url") if isinstance(sub.get("url"), str) else ""
            sub_url = _html_unescape.unescape(sub_url).strip()
            sub_name = sub.get("name") if isinstance(sub.get("name"), str) else ""
            sub_name = _html_unescape.unescape(sub_name).strip()
            if not sub_url:
                continue
            try:
                parsed = urlparse(sub_url)
            except (ValueError, TypeError):
                continue
            if parsed.scheme.lower() not in ALLOWED_SCHEMES:
                continue
            host = (parsed.hostname or "").lower()
            if (
                host == "youtube.com"
                or host == "www.youtube.com"
                or host == "m.youtube.com"
                or host == "youtu.be"
                or host.endswith(".youtube.com")
            ):
                youtube_urls.append(sub_url)
            else:
                other_resource_urls.append((sub_url, sub_name))

        # Verbatim quote: prefer the JSON-LD description when long enough.
        verbatim_quote: Optional[str] = (
            description if description and len(description) >= VERBATIM_QUOTE_MIN_CHARS
            else None
        )
        summary = description if verbatim_quote is None else ""

        # verification_type — same classification rules, applied to the
        # description text + any subjectOf URL.
        text_for_class = " ".join(
            [description] + [u for u, _ in other_resource_urls]
        ).lower()
        if youtube_urls:
            verification_type = "youtube"
        elif "interview" in text_for_class:
            verification_type = "interview"
        elif (
            "photo" in text_for_class
            or "pedalboard" in text_for_class
            or "instagram" in text_for_class
        ):
            verification_type = "photo"
        else:
            verification_type = "unknown"

        verification_note = ""
        for _src_url, work_name in other_resource_urls:
            if work_name:
                verification_note = work_name
                break

        artist_slug = _slugify(artist_name)
        chunk_id = f"eb-{slug}-artist-{artist_slug}"
        chunk = {
            "id": chunk_id,
            "type": "artist_usage",
            "source": "equipboard",
            "content": {
                "artist": artist_name,
                "artist_roles": [],
                "associated_act": "",
                "verification_type": verification_type,
                "verification_note": verification_note,
                "verbatim_quote": verbatim_quote,
                "summary": summary,
                "alternatives_recommended": [],
            },
            "tier_used": tier_used,
            "provenance": provenance_factory(f"#artist-{artist_slug}"),
        }
        chunks.append(chunk)
        records.append((person, youtube_urls, chunk_id))

    return chunks, records


def _find_used_with_from_dom(soup: BeautifulSoup) -> list[str]:
    """Live 2026 fallback: pull gear names out of `#eb-item-page-used-with-container`
    via the per-item `<a href="/items/...">` anchors."""
    container = soup.find(id="eb-item-page-used-with-container")
    if container is None:
        container = soup.find(id="usedWith")
    if container is None:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for a in container.find_all("a", href=True):
        href = a.get("href") or ""
        if not href.startswith("/items/"):
            continue
        # Skip image-link anchors (no text content).
        text = " ".join(a.stripped_strings).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        names.append(text)
    return names


def _find_similar_from_dom(soup: BeautifulSoup) -> list[str]:
    """Live 2026 fallback: pull gear names out of the curated similar-items
    container (`.eb-item-page-curated-similar-items-container`)."""
    container = soup.find(
        class_=lambda c: bool(c)
        and "eb-item-page-curated-similar-items-container" in c
    )
    if container is None:
        # As a deeper fallback try the swiper, but that one carries the
        # "More Boss Flanger Effects Pedals" rail rather than the curated
        # alternatives — only use it when the curated container is missing.
        container = soup.find(id="similarProducts")
    if container is None:
        return []
    names: list[str] = []
    seen: set[str] = set()
    for a in container.find_all("a", href=True):
        href = a.get("href") or ""
        if not href.startswith("/items/"):
            continue
        # Prefer `title=` (set on the anchor), fall back to anchor text.
        text = a.get("title") or " ".join(a.stripped_strings).strip()
        text = (text or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        names.append(text)
    return names


def parse_to_chunks(fetch_result: dict, gear_ctx: dict) -> list[dict]:
    """Convert a successfully-fetched Equipboard item page into chunks.

    See module docstring for the chunk-type contract. Every chunk carries
    `source: "equipboard"`, `tier_used: fetch_result.get("tier", 1)`,
    `provenance.url`, `provenance.section`, `provenance.scraped_at`.

    Live 2026 selector strategy (after the Phase-3 smoke regression):

    1. **JSON-LD `@graph` first** — Equipboard ships a load-bearing
       `<script type="application/ld+json">` block whose `@graph` includes
       the canonical artist `ItemList` (`@id` ending in `#artistUsage`) and
       Product description. This is dramatically more stable than the
       Tailwind class names which the Equipboard team rotates routinely.
    2. **DOM fallback for used_with / similar** — the JSON-LD does NOT
       include the Used-With rollup or the curated Similar list. Those are
       extracted from `#eb-item-page-used-with-container` and
       `.eb-item-page-curated-similar-items-container` respectively.
    3. **Legacy synthetic-DOM path** — when neither JSON-LD nor the live
       containers are present (e.g., the original `equipboard_sample.html`
       synthetic fixture), the original `_find_artist_blocks` /
       `_find_used_with` / `_find_similar_in_category` selectors run as a
       last resort. Keeps the 11 pre-existing tests green.
    """
    body = fetch_result.get("body")
    if not isinstance(body, str) or not body:
        return []

    soup = BeautifulSoup(body, "html.parser")

    url = fetch_result.get("url_attempted") or ""
    slug = _slug_from_url(url)
    scraped_at = gear_ctx.get("scraped_at", "")
    from_gear = gear_ctx.get("item") or gear_ctx.get("brand") or slug

    # tier_used defaults to 1; tier-2/3 callers (Plan 05) will pass the
    # actual tier in fetch_result["tier"].
    tier_used = fetch_result.get("tier", 1)

    def _provenance(section: str) -> dict:
        return {
            "url": url,
            "section": section,
            "scraped_at": scraped_at,
        }

    chunks: list[dict] = []

    # ----- 1. Description (JSON-LD Product first, DOM fallback) -----
    description = _find_jsonld_product_description(soup) or _find_description(soup)
    if description:
        chunks.append(
            {
                "id": f"eb-{slug}-c01",
                "type": "text",
                "source": "equipboard",
                "content": description,
                "tier_used": tier_used,
                "provenance": _provenance("description"),
            }
        )

    # ----- 2. Artist-usage (JSON-LD ItemList first, DOM fallback) -----
    artist_block_records: list[tuple[Any, list[str], str]] = []
    jsonld_artists = _find_artist_itemlist(soup)
    if jsonld_artists is not None:
        jsonld_chunks, jsonld_records = _build_artist_chunks_from_jsonld(
            jsonld_artists, slug, tier_used, _provenance
        )
        chunks.extend(jsonld_chunks)
        artist_block_records.extend(jsonld_records)
    else:
        artist_block_records.extend(
            _parse_artists_from_dom(soup, slug, tier_used, _provenance, chunks)
        )

    # ----- 3. Used With cross_ref (JSON-LD has none; DOM-only) -----
    used_with = _find_used_with_from_dom(soup) or _find_used_with(soup)
    if used_with:
        chunks.append(
            {
                "id": f"eb-{slug}-used-with",
                "type": "cross_ref",
                "source": "equipboard",
                "content": {
                    "from_gear": from_gear,
                    "relation": "used_with",
                    "to_gear": used_with,
                    "weight": None,
                },
                "tier_used": tier_used,
                "provenance": _provenance("#used-with"),
            }
        )

    # ----- 4. Similar in category cross_ref (JSON-LD has none; DOM-only) -----
    similar = _find_similar_from_dom(soup) or _find_similar_in_category(soup)
    if similar:
        chunks.append(
            {
                "id": f"eb-{slug}-similar",
                "type": "cross_ref",
                "source": "equipboard",
                "content": {
                    "from_gear": from_gear,
                    "relation": "similar_in_category",
                    "to_gear": similar,
                    "weight": None,
                },
                "tier_used": tier_used,
                "provenance": _provenance("#similar-in-category"),
            }
        )

    # ----- 5. external_resource chunks for YouTube links in artist blocks -----
    ext_counter = 1
    for _block, yt_urls, parent_chunk_id in artist_block_records:
        for yt_url in yt_urls:
            parent_chunk = next(
                (c for c in chunks if c["id"] == parent_chunk_id), None
            )
            creator = ""
            if parent_chunk is not None:
                creator = parent_chunk["content"].get("artist", "")
            chunks.append(
                {
                    "id": f"eb-{slug}-ext-{ext_counter:02d}",
                    "type": "external_resource",
                    "source": "equipboard",
                    "content": {
                        "resource_type": "youtube",
                        "creator": creator,
                        "title": "",
                        "url": yt_url,
                        "updated": None,
                        "relevance": "artist_usage_citation",
                        "citing_chunk_ids": [parent_chunk_id],
                    },
                    "tier_used": tier_used,
                    "provenance": _provenance(f"#artist-{_slugify(creator)}"),
                }
            )
            ext_counter += 1

    return chunks


def _parse_artists_from_dom(
    soup: BeautifulSoup,
    slug: str,
    tier_used: int,
    provenance_factory,
    chunks: list[dict],
) -> list[tuple[Any, list[str], str]]:
    """Legacy synthetic-DOM parser. Used only when JSON-LD is unavailable.
    Mutates `chunks` (appends artist_usage entries) and returns the
    artist_block_records list used to backlink external_resource chunks."""
    records: list[tuple[Any, list[str], str]] = []
    artist_blocks = _find_artist_blocks(soup)

    for block in artist_blocks:
        name_node = block.find(class_="artist-name")
        if name_node is None:
            name_node = block.find(["h3", "h4"])
        if name_node is None:
            continue
        artist_name = " ".join(name_node.stripped_strings).strip()
        if not _is_plausible_artist_name(artist_name):
            continue

        roles = _parse_roles(block)
        alternatives = _parse_alternatives(block)
        youtube_urls = _extract_youtube_urls(block)
        verification_type = _verification_type(block, bool(youtube_urls))

        # Verbatim quote: longest string >= VERBATIM_QUOTE_MIN_CHARS.
        quote_node = block.find(class_="verbatim-quote")
        verbatim_quote: Optional[str] = None
        if quote_node is not None:
            text = " ".join(quote_node.stripped_strings).strip()
            if text and len(text) >= VERBATIM_QUOTE_MIN_CHARS:
                verbatim_quote = text

        if verbatim_quote is None:
            longest = _longest_text(block)
            if len(longest) >= VERBATIM_QUOTE_MIN_CHARS:
                verbatim_quote = longest

        all_strings = list(block.stripped_strings)
        if verbatim_quote:
            summary_parts = [
                s for s in all_strings
                if s != verbatim_quote and s != artist_name
            ]
        else:
            summary_parts = [s for s in all_strings if s != artist_name]
        summary = " ".join(summary_parts).strip()

        verification_note = ""
        for s in all_strings:
            if s == artist_name or s == verbatim_quote:
                continue
            low = s.lower()
            if (
                "video review" in low
                or "interview" in low
                or "photo" in low
                or "pedalboard" in low
            ):
                verification_note = s
                break

        artist_slug = _slugify(artist_name)
        chunk_id = f"eb-{slug}-artist-{artist_slug}"
        chunks.append(
            {
                "id": chunk_id,
                "type": "artist_usage",
                "source": "equipboard",
                "content": {
                    "artist": artist_name,
                    "artist_roles": roles,
                    "associated_act": "",
                    "verification_type": verification_type,
                    "verification_note": verification_note,
                    "verbatim_quote": verbatim_quote,
                    "summary": summary,
                    "alternatives_recommended": alternatives,
                },
                "tier_used": tier_used,
                "provenance": provenance_factory(f"#artist-{artist_slug}"),
            }
        )
        records.append((block, youtube_urls, chunk_id))

    return records


# ---------------------------------------------------------------------------
# Self-registration (idempotent)
# ---------------------------------------------------------------------------
# Per source-class-registry.md, each module appends itself to REGISTRY on
# import. Guarded against double-registration so importlib.reload() in tests
# does not duplicate the entry. Copied verbatim from `reddit.py` per the
# Plan 02 pattern.

from . import REGISTRY as _REGISTRY  # noqa: E402

_self = sys.modules[__name__]
if _self not in _REGISTRY:
    _REGISTRY.append(_self)
