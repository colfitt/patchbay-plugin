"""Test suite for canonicalize_url — pure URL canonicalization for citations.

Covers CITATION-04 (URL canonicalization collapses YouTube long/short, ?si=,
trailing slash variants) and T-04-01 (non-http(s) scheme rejection).

12 cases locked at v2.0. Run with:

    python -m pytest skills/patchbay-research/scripts/test_canonicalize_url.py -v
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pytest  # noqa: E402

from canonicalize_url import canonicalize_url  # noqa: E402


def test_canonicalize_youtube_long_to_short():
    """youtu.be/<id> and www.youtube.com/watch?v=<id> collapse to the same canonical form."""
    long_form = canonicalize_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    short_form = canonicalize_url("https://youtu.be/dQw4w9WgXcQ")
    assert long_form == short_form
    assert long_form == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_canonicalize_strips_si_tracking_param():
    """?si=... is YouTube's share-tracking parameter — must be stripped."""
    with_si = canonicalize_url("https://youtu.be/abc123XYZ?si=xyz789")
    without_si = canonicalize_url("https://youtu.be/abc123XYZ")
    assert with_si == without_si


def test_canonicalize_strips_trailing_slash():
    """A single trailing slash on a non-root path is stripped."""
    with_slash = canonicalize_url("https://example.com/article/")
    without_slash = canonicalize_url("https://example.com/article")
    assert with_slash == without_slash


def test_canonicalize_strips_trailing_slash_youtube_short():
    """Trailing slash on youtu.be short form collapses to the same canonical form."""
    with_slash = canonicalize_url("https://youtu.be/abc123XYZ/")
    without_slash = canonicalize_url("https://youtu.be/abc123XYZ")
    assert with_slash == without_slash


def test_canonicalize_preserves_other_query_params():
    """utm_* trackers are stripped; non-tracking query params are preserved."""
    result = canonicalize_url("https://example.com/x?utm_source=foo&page=2")
    assert "utm_source" not in result
    assert "page=2" in result


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/abc123XYZ?si=xyz789",
    "https://example.com/article/",
    "https://example.com/x?utm_source=foo&page=2",
    "HTTPS://Www.YouTube.com/watch?v=X",
])
def test_canonicalize_idempotent(url):
    """canonicalize_url(canonicalize_url(u)) == canonicalize_url(u)."""
    once = canonicalize_url(url)
    twice = canonicalize_url(once)
    assert once == twice


def test_canonicalize_preserves_scheme_case_insensitive():
    """HTTPS is lower-cased to https; http stays http."""
    https_upper = canonicalize_url("HTTPS://example.com/x")
    https_lower = canonicalize_url("https://example.com/x")
    assert https_upper == https_lower
    assert https_lower.startswith("https://")
    http_lower = canonicalize_url("http://example.com/x")
    assert http_lower.startswith("http://")


def test_canonicalize_lowercases_host():
    """Host is normalized to lowercase regardless of input casing."""
    result = canonicalize_url("HTTPS://Www.YouTube.com/watch?v=X")
    assert "www.youtube.com" in result
    assert "Www.YouTube.com" not in result


def test_canonicalize_handles_youtube_extra_params():
    """v= and t= are preserved (content-relevant); feature= is stripped (tracking)."""
    result = canonicalize_url("https://www.youtube.com/watch?v=X&t=42s&feature=share")
    assert "v=X" in result
    assert "t=42s" in result
    assert "feature" not in result


def test_canonicalize_rejects_non_http_schemes():
    """javascript:, data:, file: schemes return '' so callers can filter."""
    assert canonicalize_url("javascript:alert(1)") == ""
    assert canonicalize_url("data:text/html,foo") == ""
    assert canonicalize_url("file:///etc/passwd") == ""


def test_canonicalize_rejects_malformed():
    """Unparseable strings return ''."""
    assert canonicalize_url("not a url at all") == ""


def test_canonicalize_rejects_empty():
    """Empty string returns ''."""
    assert canonicalize_url("") == ""
    assert canonicalize_url("   ") == ""
