"""canonicalize_url — collapse URL variants so two chunks pointing at the
same resource count as one citation, not two. Library-light pure function;
no requests / no network. T-04-01 mitigation: rejects non-http(s) schemes
(returns "" so callers can filter).

CITATION-04: this is the single source of truth for URL canonicalization
across patchbay:research. The external_resource_sweep dedupes by this
function's output; downstream Plan 02 (recommendations) and Plan 03
(verified promotion) inherit the canonicalization for free.

Canonicalization rules (locked at v2.0):
  - Reject non-http(s) schemes (javascript:, data:, file:, etc.) → "".
  - Lowercase scheme + host.
  - youtu.be/<id>  ↔  www.youtube.com/watch?v=<id>  (canonical = the watch form).
  - All other YouTube hosts (m.youtube.com, youtube.com) normalize to
    www.youtube.com.
  - Strip TRACKING_PARAMS from the query (si, utm_*, feature, fbclid, ...).
  - Strip a single trailing slash from a non-root path.
  - Preserve remaining query params; sort for determinism.
  - Drop URL fragment (#section) — deep_link lives in provenance, not the
    citation key.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


# Tracking params stripped across ALL hosts. Source: locked at v2.0 per
# CITATION-04 + spike findings. Keep this list small — adding a host-
# specific param means a host-specific case below, not a new entry here.
TRACKING_PARAMS = frozenset({
    "si",                            # YouTube share-tracking
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "feature",                       # YouTube share-feature attribution
    "fbclid", "gclid", "mc_cid", "mc_eid",  # common ad/email trackers
})

YOUTUBE_HOSTS = frozenset({"www.youtube.com", "youtube.com", "m.youtube.com"})


def canonicalize_url(url: str) -> str:
    """Return the canonical form of `url`, or "" if `url` is unusable.

    See module docstring for the full rule list. The function is pure and
    deterministic — same input always yields the same output.
    """
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        p = urlparse(url.strip())
    except (ValueError, TypeError):
        return ""

    scheme = (p.scheme or "").lower()
    if scheme not in ("http", "https"):
        return ""

    host = (p.hostname or "").lower()
    if not host:
        return ""

    path = p.path or ""
    query_pairs = parse_qsl(p.query, keep_blank_values=False)

    # YouTube short → long canonicalization.
    if host == "youtu.be" and path and path != "/":
        video_id = path.strip("/").split("/")[0]
        if video_id:
            host = "www.youtube.com"
            path = "/watch"
            # Drop any existing v=, prepend our extracted one.
            query_pairs = [("v", video_id)] + [
                (k, v) for k, v in query_pairs if k != "v"
            ]
    elif host in YOUTUBE_HOSTS:
        # Normalize host to www.youtube.com for the watch URL form.
        host = "www.youtube.com"

    # Strip tracking params.
    query_pairs = [(k, v) for k, v in query_pairs if k not in TRACKING_PARAMS]
    # Deterministic ordering.
    query_pairs.sort()
    query = urlencode(query_pairs)

    # Strip a single trailing slash from non-root paths.
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")

    # Rebuild. Drop fragment (collapses #section variants; deep_link lives
    # in provenance, not in the canonical citation key).
    return urlunparse((scheme, host, path, "", query, ""))
