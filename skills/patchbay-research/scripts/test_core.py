"""Test suite for the tier-1 core of `/patchbay:research`.

Covers RESEARCH-02 (tier-1 + failure logging classification), RESEARCH-03
(failures.log nine-field schema), and RESEARCH-09 (cross-source corroboration).

All tests are self-contained — they import from sibling modules under
`skills/patchbay-research/scripts/`. Run with:

    python -m pytest skills/patchbay-research/scripts/test_core.py -v
"""

import json
import os
import sys
import types
from pathlib import Path

import pytest
import requests

# Make sibling scripts importable regardless of cwd.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from log_failure import classify_reason, log_failure  # noqa: E402
from url_router import route_url  # noqa: E402
from write_chunk import (  # noqa: E402
    compute_cross_source_matches,
    update_chunk_field,
    write_chunks,
)


# ---------------------------------------------------------------------------
# log_failure.classify_reason
# ---------------------------------------------------------------------------

def test_classify_cloudflare():
    reason, suggested = classify_reason(403, "Just a moment...", None)
    assert reason == "cloudflare-block"
    assert suggested == 2


def test_classify_404():
    reason, suggested = classify_reason(404, "<html>Not found</html>", None)
    assert reason == "404"
    assert suggested == "skip"


def test_classify_timeout():
    exc = requests.Timeout("read timed out")
    reason, suggested = classify_reason(0, "", exc)
    assert reason == "timeout"
    assert suggested == "either"


# ---------------------------------------------------------------------------
# log_failure.log_failure (nine-field schema)
# ---------------------------------------------------------------------------

def test_log_failure_writes_jsonl(tmp_path):
    # The path-containment check requires the log file to live under a
    # `<gear_root>/<Brand Item>/knowledge/` shape. Build that under tmp_path.
    gear_root = tmp_path / "Gear"
    knowledge = gear_root / "Boss BF-3" / "knowledge"
    knowledge.mkdir(parents=True)
    failures_log = knowledge / "failures.log"

    log_failure(
        str(failures_log),
        url="https://equipboard.com/items/chase-bliss-clean",
        status=403,
        body="Just a moment... Checking your browser",
        exc=None,
        gear_root=str(gear_root),
    )

    lines = failures_log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])

    # All nine fields present
    for field in (
        "timestamp",
        "url",
        "tier_attempted",
        "http_status",
        "reason",
        "reason_detail",
        "suggested_escalation",
        "last_attempted",
        "retry_count",
    ):
        assert field in entry, f"missing field: {field}"

    assert entry["tier_attempted"] == 1
    assert entry["retry_count"] == 1
    assert entry["timestamp"].endswith("Z")
    assert entry["last_attempted"].endswith("Z")
    # ISO-8601 shape: YYYY-MM-DDTHH:MM:SS(.ffffff)?Z
    assert "T" in entry["timestamp"]
    assert entry["reason"] == "cloudflare-block"
    assert entry["suggested_escalation"] == 2


# ---------------------------------------------------------------------------
# write_chunk.compute_cross_source_matches
# ---------------------------------------------------------------------------

def test_cross_source_matches_finds_shared_artist():
    existing = [
        {
            "id": "eb-cb-clean-c01",
            "type": "artist_usage",
            "source": "equipboard",
            "content": {
                "artist": "Rhett Shull",
                "summary": "Rhett positions Clean as an amazing compressor.",
            },
            "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
        }
    ]
    new_chunk = {
        "id": "rd-clean-review-c01",
        "type": "review_section",
        "source": "reddit",
        "content": "Rhett Shull mentioned this pedal in his YouTube review.",
        "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
    }
    matches = compute_cross_source_matches(new_chunk, existing)
    assert "Rhett Shull" in matches


def test_cross_source_matches_caps_runaway_titlecase_blob():
    """Regression: in the Phase-3 production smoke, one equipboard
    `artist_usage` chunk had a plaintext-extracted `summary` containing every
    comma-separated artist name on the page. The TitleCase pass in
    `_extract_names_from_content` produced 199 candidates against an existing
    haystack that mentioned every artist — every comma-separated token
    became a match. Even when the upstream parser is healthier, a single
    chunk MUST NOT be able to fan out to hundreds of candidates. Pin the
    cap at MAX_NAME_CANDIDATES (25)."""
    from write_chunk import MAX_NAME_CANDIDATES

    # Build a giant TitleCase-heavy summary that mimics the live smoke's
    # 'artist-album-usage' megablob — every two-word capitalized token will
    # be lifted by the TitleCase regex.
    fake_names = [f"Artist Name{i:03d}" for i in range(300)]
    new_chunk = {
        "id": "eb-bf3-artist-blob",
        "type": "artist_usage",
        "source": "equipboard",
        "content": {
            "artist": "Album Usage",
            "summary": ", ".join(fake_names),
        },
        "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
    }
    # Existing haystack contains every fake name verbatim — without a cap
    # the bidirectional scan returns 300+ matches.
    existing = [
        {
            "id": "manual-bf3-c01",
            "type": "text",
            "source": "manual",
            "content": ", ".join(fake_names),
            "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
        }
    ]
    matches = compute_cross_source_matches(new_chunk, existing)
    assert len(matches) <= MAX_NAME_CANDIDATES, (
        f"expected <={MAX_NAME_CANDIDATES} matches; got {len(matches)} — "
        f"runaway TitleCase extraction is not capped"
    )
    assert MAX_NAME_CANDIDATES <= 50, (
        f"MAX_NAME_CANDIDATES={MAX_NAME_CANDIDATES} is too permissive — "
        f"the whole point of the cap is to reject 100+ match clusters"
    )


def test_cross_source_matches_empty_when_no_overlap():
    existing = [
        {
            "id": "eb-foo-c01",
            "type": "text",
            "source": "equipboard",
            "content": "Some unrelated content about reverb pedals.",
            "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
        }
    ]
    new_chunk = {
        "id": "rd-bar-c01",
        "type": "text",
        "source": "reddit",
        "content": "Totally different topic entirely.",
        "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
    }
    assert compute_cross_source_matches(new_chunk, existing) == []


# ---------------------------------------------------------------------------
# write_chunk.write_chunks
# ---------------------------------------------------------------------------

def test_write_chunks_appends_jsonl(tmp_path):
    gear_root = tmp_path / "Gear"
    knowledge = gear_root / "Boss BF-3" / "knowledge"
    knowledge.mkdir(parents=True)
    chunks_path = knowledge / "chunks.jsonl"

    chunks = [
        {
            "id": "eb-bf3-c01",
            "type": "text",
            "source": "equipboard",
            "content": "Rhett Shull demoed the BF-3.",
            "provenance": {
                "url": "https://equipboard.com/items/boss-bf-3",
                "scraped_at": "2026-05-15T00:00:00Z",
            },
        },
        {
            "id": "rd-bf3-c01",
            "type": "text",
            "source": "reddit",
            "content": "Rhett Shull's BF-3 review covered the flanger modes.",
            "provenance": {
                "url": "https://reddit.com/r/guitarpedals/comments/abc/",
                "scraped_at": "2026-05-15T00:00:00Z",
            },
        },
    ]

    result = write_chunks(str(chunks_path), chunks, gear_root=str(gear_root))
    assert result["written"] == 2

    lines = chunks_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        parsed = json.loads(line)
        assert "cross_source_match_candidates" in parsed

    # Second chunk should match the artist from the first.
    second = json.loads(lines[1])
    assert "Rhett Shull" in second["cross_source_match_candidates"]


# ---------------------------------------------------------------------------
# write_chunk.update_chunk_field (used by YouTube two-pass enrichment in Plan 04)
# ---------------------------------------------------------------------------

def test_update_chunk_field_dotted_path(tmp_path):
    gear_root = tmp_path / "Gear"
    knowledge = gear_root / "Boss BF-3" / "knowledge"
    knowledge.mkdir(parents=True)
    chunks_path = knowledge / "chunks.jsonl"

    chunks_path.write_text(
        json.dumps(
            {
                "id": "yt-mm-001",
                "type": "multimodal_segment",
                "source": "youtube",
                "content": {"frame_description": "old", "caption_text": "x"},
                "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    update_chunk_field(
        str(chunks_path),
        "yt-mm-001",
        "content.frame_description",
        "new description after second pass",
        gear_root=str(gear_root),
    )

    updated = json.loads(chunks_path.read_text(encoding="utf-8").splitlines()[0])
    assert updated["content"]["frame_description"] == "new description after second pass"
    assert updated["content"]["caption_text"] == "x"  # unchanged


# ---------------------------------------------------------------------------
# url_router.route_url
# ---------------------------------------------------------------------------

def _make_module(name, match_fn):
    mod = types.ModuleType(name)
    mod.match_url = match_fn
    mod.fetch_tier1 = lambda url: {"status": 200, "body": "", "headers": {}, "elapsed_ms": 0}
    mod.parse_to_chunks = lambda result, ctx: []
    return mod


def test_route_url_matches_reddit():
    generic = _make_module("generic", lambda url: False)
    reddit = _make_module("reddit", lambda url: "reddit.com" in url)
    registry = [reddit, generic]

    selected = route_url("https://reddit.com/r/guitarpedals/comments/abc/", registry)
    assert selected is reddit


def test_route_url_fallback_to_generic():
    generic = _make_module("generic", lambda url: False)
    reddit = _make_module("reddit", lambda url: "reddit.com" in url)
    registry = [reddit, generic]

    selected = route_url("https://unknown-site.example.com/foo", registry)
    assert selected is generic


# ---------------------------------------------------------------------------
# Security: fetch_tier1 SSRF guards (T-03-01)
# ---------------------------------------------------------------------------

def test_fetch_tier1_rejects_non_http_scheme():
    from fetch_tier1 import fetch_tier1
    with pytest.raises(ValueError):
        fetch_tier1("file:///etc/passwd")


def test_fetch_tier1_rejects_private_ip():
    from fetch_tier1 import fetch_tier1
    with pytest.raises(ValueError):
        fetch_tier1("http://127.0.0.1/admin")
