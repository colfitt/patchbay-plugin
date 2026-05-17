"""Tests for the Equipboard source class (Plan 03-03).

Eleven named cases, locked in the plan's <acceptance_criteria>:

 1. test_match_url_accepts_canonical
 2. test_match_url_rejects_non_item_path
 3. test_match_url_rejects_substring_host
 4. test_match_url_rejects_non_https_scheme
 5. test_fetch_tier1_returns_cloudflare_block_unchanged
 6. test_parse_emits_artist_usage
 7. test_parse_emits_used_with_cross_ref
 8. test_parse_emits_similar_cross_ref
 9. test_parse_emits_external_resource_for_youtube_in_artist_block
10. test_init_py_contains_equipboard_append_and_preserves_others
11. test_equipboard_self_registers_into_registry
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Make `skills/patchbay-research` importable as a top-level package root so
# `source_classes` and `scripts` resolve regardless of cwd.
_RESEARCH_ROOT = Path(__file__).resolve().parent.parent
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "equipboard_sample.html"


def _load_fetch_result(url: str = "https://equipboard.com/items/chase-bliss-clean") -> dict:
    body_text = FIXTURE_PATH.read_text(encoding="utf-8")
    return {
        "status": 200,
        "body": body_text,
        "json": None,
        "url_attempted": url,
        "headers": {},
        "elapsed_ms": 12,
        "exc": None,
    }


def _gear_ctx() -> dict:
    return {
        "gear_slug": "chase-bliss-clean",
        "brand": "Chase Bliss Audio",
        "item": "Chase Bliss Audio Clean",
        "scraped_at": "2026-05-16T02:30:00Z",
    }


# ---------------------------------------------------------------------------
# match_url
# ---------------------------------------------------------------------------


def test_match_url_accepts_canonical():
    from source_classes import equipboard
    assert equipboard.match_url(
        "https://equipboard.com/items/chase-bliss-clean"
    ) is True


def test_match_url_rejects_non_item_path():
    from source_classes import equipboard
    assert equipboard.match_url(
        "https://equipboard.com/artists/foo"
    ) is False


def test_match_url_rejects_substring_host():
    from source_classes import equipboard
    assert equipboard.match_url(
        "https://equipboard.com.attacker.io/items/x"
    ) is False


def test_match_url_rejects_non_https_scheme():
    from source_classes import equipboard
    assert equipboard.match_url("javascript:alert(1)") is False


# ---------------------------------------------------------------------------
# fetch_tier1
# ---------------------------------------------------------------------------


def test_fetch_tier1_returns_cloudflare_block_unchanged():
    """When the shared helper returns a 403 + Cloudflare body, equipboard's
    fetch_tier1 forwards it as-is — classification happens at log_failure time.
    """
    from source_classes import equipboard

    cloudflare_body = (
        "<html><head><title>Just a moment...</title></head>"
        "<body>Checking your browser before accessing equipboard.com.</body></html>"
    )

    def fake_shared_fetch(url: str) -> dict:
        return {
            "status": 403,
            "body": cloudflare_body,
            "headers": {"server": "cloudflare"},
            "elapsed_ms": 220,
            "exc": None,
        }

    with patch.object(equipboard, "_shared_fetch_tier1", side_effect=fake_shared_fetch):
        result = equipboard.fetch_tier1(
            "https://equipboard.com/items/chase-bliss-clean"
        )

    assert result["status"] == 403
    assert "Just a moment..." in result["body"]
    assert result["url_attempted"] == "https://equipboard.com/items/chase-bliss-clean"


# ---------------------------------------------------------------------------
# parse_to_chunks
# ---------------------------------------------------------------------------


def test_parse_emits_artist_usage():
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(_load_fetch_result(), _gear_ctx())
    artist_chunks = [c for c in chunks if c["type"] == "artist_usage"]
    assert len(artist_chunks) >= 2, chunks
    # At least one of the artist blocks has a verbatim quote captured.
    with_quote = [
        c for c in artist_chunks
        if c["content"].get("verbatim_quote")
    ]
    assert len(with_quote) >= 1, artist_chunks
    # Each artist_usage chunk has the locked surface
    for c in artist_chunks:
        assert c["source"] == "equipboard"
        assert c["tier_used"] == 1
        assert "url" in c["provenance"]
        assert "section" in c["provenance"]
        assert c["provenance"]["scraped_at"] == "2026-05-16T02:30:00Z"
        assert "artist" in c["content"]
        assert "artist_roles" in c["content"]
        assert "verification_type" in c["content"]


def test_parse_emits_used_with_cross_ref():
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(_load_fetch_result(), _gear_ctx())
    used_with = [
        c for c in chunks
        if c["type"] == "cross_ref"
        and c["content"]["relation"] == "used_with"
    ]
    assert len(used_with) == 1, chunks
    content = used_with[0]["content"]
    assert content["from_gear"] == "Chase Bliss Audio Clean"
    assert content["weight"] is None
    assert isinstance(content["to_gear"], list)
    assert len(content["to_gear"]) >= 3
    # ID format
    assert used_with[0]["id"] == "eb-chase-bliss-clean-used-with"


def test_parse_emits_similar_cross_ref():
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(_load_fetch_result(), _gear_ctx())
    similar = [
        c for c in chunks
        if c["type"] == "cross_ref"
        and c["content"]["relation"] == "similar_in_category"
    ]
    assert len(similar) == 1, chunks
    content = similar[0]["content"]
    assert content["from_gear"] == "Chase Bliss Audio Clean"
    assert isinstance(content["to_gear"], list)
    assert len(content["to_gear"]) >= 3
    assert similar[0]["id"] == "eb-chase-bliss-clean-similar"


def test_parse_emits_external_resource_for_youtube_in_artist_block():
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(_load_fetch_result(), _gear_ctx())
    ext = [c for c in chunks if c["type"] == "external_resource"]
    youtube = [c for c in ext if c["content"]["resource_type"] == "youtube"]
    assert len(youtube) >= 1, ext
    yt = youtube[0]
    assert "youtube.com/watch?v=ABC123XYZ" in yt["content"]["url"]
    # citing_chunk_ids must reference the enclosing artist_usage chunk
    assert isinstance(yt["content"]["citing_chunk_ids"], list)
    assert len(yt["content"]["citing_chunk_ids"]) >= 1
    citing_id = yt["content"]["citing_chunk_ids"][0]
    artist_ids = {
        c["id"] for c in chunks if c["type"] == "artist_usage"
    }
    assert citing_id in artist_ids, (citing_id, artist_ids)
    # The creator field should carry the enclosing artist's name
    assert yt["content"]["creator"] == "Rhett Shull"
    assert yt["content"]["relevance"] == "artist_usage_citation"


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_init_py_contains_equipboard_append_and_preserves_others():
    init_path = _RESEARCH_ROOT / "source_classes" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    # Plan 01's scaffold must remain untouched.
    assert "REGISTRY: list = []" in text
    # Plan 02's append must still be present (no clobbering).
    assert "from . import reddit" in text
    # Plan 03's single-line append must be present.
    assert "from . import equipboard" in text


def test_equipboard_self_registers_into_registry():
    # Fresh import sequence mirrors how `__init__.py`'s `from . import
    # equipboard` line behaves on a cold start. Reload both `source_classes`
    # AND `equipboard` so the module body runs against the freshly-reset list.
    import importlib
    import source_classes as sc
    importlib.reload(sc)
    from source_classes import equipboard as equipboard_mod
    importlib.reload(equipboard_mod)
    assert equipboard_mod in sc.REGISTRY, (
        "equipboard module did not self-register into source_classes.REGISTRY"
    )


# ---------------------------------------------------------------------------
# Live 2026 DOM regression suite
# ---------------------------------------------------------------------------
# These tests load `equipboard_live_2026.html` — the actual HTML captured
# from `equipboard.com/items/boss-bf-3-flanger-pedal` during the Phase-3
# Plan 05 production smoke (2026-05-17). The synthetic fixture
# `equipboard_sample.html` uses an older / simpler DOM shape; the live page
# uses Tailwind CSS classes AND embeds a load-bearing JSON-LD `@graph` with
# the canonical artist list. These tests pin the parser to the live shape so
# selector drift surfaces immediately.
# ---------------------------------------------------------------------------

LIVE_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "equipboard_live_2026.html"
)


def _load_live_fetch_result() -> dict:
    body_text = LIVE_FIXTURE_PATH.read_text(encoding="utf-8")
    return {
        "status": 200,
        "body": body_text,
        "json": None,
        "url_attempted": (
            "https://equipboard.com/items/boss-bf-3-flanger-pedal"
        ),
        "headers": {},
        "elapsed_ms": 12,
        "exc": None,
        "tier": 2,
    }


def _live_gear_ctx() -> dict:
    return {
        "gear_slug": "boss-bf-3-flanger-pedal",
        "brand": "Boss",
        "item": "Boss BF-3 Flanger",
        "scraped_at": "2026-05-17T13:00:00Z",
    }


# Verified artists from the live 2026 JSON-LD `#artistUsage` ItemList.
# These names are the load-bearing knowledge graph — the parser missing
# them was the headline regression in the Phase-3 smoke.
_VERIFIED_LIVE_ARTISTS = {
    "Billie Joe Armstrong",
    "Jonny Greenwood",
    "Steve Vai",
    "Robert Smith",
    "Adam Jones",
    "Thomas DeLonge",
    "Stephen Carpenter",
    "Mark Hoppus",
    "Pat Smear",
    "Brad Delson",
    "Bruce Springsteen",
    "Simon Gallup",
}


def test_parse_live_2026_emits_at_least_10_named_artist_chunks():
    """Live 2026 DOM regression. The parser MUST produce at least 10 named
    `artist_usage` chunks AND must capture at least 8 of the known verified
    artists from the JSON-LD `#artistUsage` ItemList. The pre-fix parser
    captured 'Album Usage' and missed all of these — this test pins that
    behavior so any selector drift fails loudly.
    """
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(
        _load_live_fetch_result(), _live_gear_ctx()
    )
    artist_chunks = [c for c in chunks if c["type"] == "artist_usage"]
    assert len(artist_chunks) >= 10, (
        f"expected >=10 named artist_usage chunks; got {len(artist_chunks)}: "
        f"{[c['content'].get('artist') for c in artist_chunks]}"
    )
    names = {c["content"].get("artist", "") for c in artist_chunks}
    matched = names & _VERIFIED_LIVE_ARTISTS
    assert len(matched) >= 8, (
        f"expected >=8 of {sorted(_VERIFIED_LIVE_ARTISTS)} in extracted "
        f"artist names; got matched={sorted(matched)} / extracted={sorted(names)}"
    )
    # Guard the headline regression: "Album Usage" / "Artist usage" /
    # similar section-heading strings must NEVER appear as artist names.
    forbidden_substrings = {"album usage", "artist usage", "load more"}
    for name in names:
        low = name.lower()
        assert all(f not in low for f in forbidden_substrings), (
            f"section-heading text {name!r} leaked into artist_usage chunk"
        )


def test_parse_live_2026_emits_used_with_cross_ref():
    """Live 2026 DOM has a `#usedWith` rollup with anchors to other
    `/items/<slug>` gear. The parser must emit ONE `cross_ref` chunk with
    `relation: used_with` and a populated `to_gear` list."""
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(
        _load_live_fetch_result(), _live_gear_ctx()
    )
    used_with = [
        c for c in chunks
        if c["type"] == "cross_ref"
        and c["content"]["relation"] == "used_with"
    ]
    assert len(used_with) == 1, (
        f"expected exactly 1 used_with cross_ref; got {len(used_with)}"
    )
    to_gear = used_with[0]["content"]["to_gear"]
    assert isinstance(to_gear, list) and len(to_gear) >= 3, (
        f"expected >=3 entries in used_with.to_gear; got {to_gear!r}"
    )
    # Boss TU-3 Chromatic Tuner is the top entry on the live page; pin it
    # as a smoke check that the names came out of the right container.
    joined = " | ".join(to_gear).lower()
    assert "tu-3" in joined or "boss tu-3" in joined, (
        f"expected Boss TU-3 in used_with list; got {to_gear!r}"
    )


def test_parse_live_2026_emits_similar_in_category_cross_ref():
    """Live 2026 DOM has a Similar section with curated alternative items.
    The parser must emit ONE `cross_ref` chunk with
    `relation: similar_in_category` and a populated `to_gear` list."""
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(
        _load_live_fetch_result(), _live_gear_ctx()
    )
    similar = [
        c for c in chunks
        if c["type"] == "cross_ref"
        and c["content"]["relation"] == "similar_in_category"
    ]
    assert len(similar) == 1, (
        f"expected exactly 1 similar_in_category cross_ref; got {len(similar)}"
    )
    to_gear = similar[0]["content"]["to_gear"]
    assert isinstance(to_gear, list) and len(to_gear) >= 3, (
        f"expected >=3 entries in similar_in_category.to_gear; got {to_gear!r}"
    )
    joined = " | ".join(to_gear).lower()
    assert "bf-2" in joined or "boss bf-2" in joined, (
        f"expected Boss BF-2 in similar_in_category list; got {to_gear!r}"
    )


def test_parse_live_2026_emits_external_resource_for_subjectof_youtube():
    """Several artist entries in the JSON-LD have a `subjectOf` CreativeWork
    whose `url` is a YouTube link. The parser must lift those into
    `external_resource` chunks with `citing_chunk_ids` referencing the
    enclosing artist's `artist_usage` chunk."""
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(
        _load_live_fetch_result(), _live_gear_ctx()
    )
    ext = [
        c for c in chunks
        if c["type"] == "external_resource"
        and c["content"].get("resource_type") == "youtube"
    ]
    assert len(ext) >= 1, (
        f"expected >=1 YouTube external_resource chunk; got {len(ext)}"
    )
    artist_ids = {c["id"] for c in chunks if c["type"] == "artist_usage"}
    for ec in ext:
        citing = ec["content"].get("citing_chunk_ids") or []
        assert citing, (
            f"external_resource chunk missing citing_chunk_ids: {ec}"
        )
        assert citing[0] in artist_ids, (
            f"citing_chunk_id {citing[0]!r} does not reference an existing "
            f"artist_usage chunk in {sorted(artist_ids)}"
        )


def test_parse_live_2026_tier_used_is_two_when_fetched_via_tier2():
    """When fetch_result carries `tier: 2`, every chunk emitted must carry
    `tier_used: 2` (defensive tier-stamping invariant from Plan 05)."""
    from source_classes import equipboard
    chunks = equipboard.parse_to_chunks(
        _load_live_fetch_result(), _live_gear_ctx()
    )
    assert chunks, "live fixture must produce at least one chunk"
    for c in chunks:
        assert c["tier_used"] == 2, (
            f"chunk {c['id']} has tier_used={c['tier_used']!r}; expected 2"
        )
