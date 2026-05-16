"""Tests for the Reddit source class (Plan 03-02).

Twelve named cases, locked in the plan's <acceptance_criteria>:

 1. test_match_url_accepts_canonical
 2. test_match_url_accepts_old_reddit
 3. test_match_url_rejects_subreddit_listing
 4. test_match_url_rejects_substring_host
 5. test_match_url_rejects_javascript_scheme
 6. test_url_rewrite_appends_dot_json
 7. test_parse_op_text_chunk
 8. test_parse_top_comments_aggregate
 9. test_parse_external_resources
10. test_chunk_ids_follow_prefix
11. test_init_py_contains_reddit_append
12. test_reddit_self_registers_into_registry
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

# Make `skills/patchbay-research` importable as a top-level package root so
# `source_classes` and `scripts` resolve regardless of cwd.
_RESEARCH_ROOT = Path(__file__).resolve().parent.parent
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reddit_sample.json"


def _load_fixture() -> dict:
    body_text = FIXTURE_PATH.read_text(encoding="utf-8")
    return {
        "status": 200,
        "body": body_text,
        "json": json.loads(body_text),
        "url_attempted": "https://reddit.com/r/guitarpedals/comments/abc123/boss_bf3_cleanblend_review.json",
        "headers": {},
        "elapsed_ms": 12,
        "exc": None,
    }


def _gear_ctx() -> dict:
    return {
        "gear_slug": "boss-bf-3",
        "brand": "Boss",
        "item": "BF-3",
        "scraped_at": "2026-05-16T02:00:00Z",
    }


# ---------------------------------------------------------------------------
# match_url
# ---------------------------------------------------------------------------


def test_match_url_accepts_canonical():
    from source_classes import reddit
    assert reddit.match_url(
        "https://reddit.com/r/guitarpedals/comments/abc123/clean_review/"
    ) is True


def test_match_url_accepts_old_reddit():
    from source_classes import reddit
    assert reddit.match_url(
        "https://old.reddit.com/r/guitarpedals/comments/abc123/clean_review/"
    ) is True


def test_match_url_rejects_subreddit_listing():
    from source_classes import reddit
    assert reddit.match_url("https://reddit.com/r/guitarpedals/") is False


def test_match_url_rejects_substring_host():
    from source_classes import reddit
    assert reddit.match_url(
        "https://evil-reddit.com.attacker.io/r/x/comments/y"
    ) is False


def test_match_url_rejects_javascript_scheme():
    from source_classes import reddit
    assert reddit.match_url("javascript:alert(1)") is False


# ---------------------------------------------------------------------------
# fetch_tier1 — URL rewrite
# ---------------------------------------------------------------------------


def test_url_rewrite_appends_dot_json():
    """fetch_tier1 must rewrite to the .json path before issuing the request."""
    from source_classes import reddit

    captured: dict = {}

    def fake_shared_fetch(url: str) -> dict:
        captured["url"] = url
        return {
            "status": 200,
            "body": "[{\"data\":{\"children\":[]}},{\"data\":{\"children\":[]}}]",
            "headers": {},
            "elapsed_ms": 5,
            "exc": None,
        }

    with patch.object(reddit, "_shared_fetch_tier1", side_effect=fake_shared_fetch):
        reddit.fetch_tier1("https://reddit.com/r/x/comments/abc/slug/")

    assert captured["url"].endswith(".json"), captured
    assert "/.json" not in captured["url"], (
        "trailing slash must be stripped BEFORE .json is appended; "
        f"got {captured['url']!r}"
    )
    assert captured["url"] == "https://reddit.com/r/x/comments/abc/slug.json"


# ---------------------------------------------------------------------------
# parse_to_chunks
# ---------------------------------------------------------------------------


def test_parse_op_text_chunk():
    from source_classes import reddit
    chunks = reddit.parse_to_chunks(_load_fixture(), _gear_ctx())
    text_chunks = [c for c in chunks if c["type"] == "text"]
    assert len(text_chunks) == 1, chunks
    op = text_chunks[0]
    assert op["source"] == "reddit"
    assert op["tier_used"] == 1
    assert "Boss BF-3" in op["content"]
    assert "Rhett Shull" in op["content"]


def test_parse_top_comments_aggregate():
    from source_classes import reddit
    chunks = reddit.parse_to_chunks(_load_fixture(), _gear_ctx())
    aggs = [c for c in chunks if c["type"] == "comment_aggregate"]
    assert len(aggs) == 1, chunks
    content = aggs[0]["content"]
    assert isinstance(content, list)
    # Fixture has 3 comments, cap is 10.
    assert len(content) == 3
    # Sorted by ups descending.
    assert [item["ups"] for item in content] == [87, 54, 31]
    # Snippet truncation: each <= 240 chars.
    for item in content:
        assert len(item["snippet"]) <= 240
        assert "author" in item and "ups" in item


def test_parse_external_resources():
    from source_classes import reddit
    chunks = reddit.parse_to_chunks(_load_fixture(), _gear_ctx())
    ext = [c for c in chunks if c["type"] == "external_resource"]
    assert len(ext) >= 1
    youtube = [c for c in ext if c["content"]["resource_type"] == "youtube"]
    assert len(youtube) == 1, ext
    assert "youtube.com/watch?v=ABC123" in youtube[0]["content"]["url"]


def test_chunk_ids_follow_prefix():
    from source_classes import reddit
    chunks = reddit.parse_to_chunks(_load_fixture(), _gear_ctx())
    assert chunks, "expected at least one chunk"
    for c in chunks:
        assert c["id"].startswith("reddit-abc123-c"), c["id"]


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_init_py_contains_reddit_append():
    init_path = _RESEARCH_ROOT / "source_classes" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    # Plan 01's scaffold must remain untouched.
    assert "REGISTRY: list = []" in text
    # Plan 02's single-line append must be present.
    assert "from . import reddit" in text


def test_reddit_self_registers_into_registry():
    # Fresh import to guarantee the side effect ran in this process.
    import importlib
    import source_classes as sc
    importlib.reload(sc)
    from source_classes import reddit
    assert reddit in sc.REGISTRY, (
        "reddit module did not self-register into source_classes.REGISTRY"
    )
