"""Test suite for external_resource_sweep — post-write citation sweep.

Covers CITATION-01 (every external URL has an external_resource chunk with
populated citing_chunk_ids) and CITATION-04 (URLs in external_resource
chunks are canonical). 14 cases locked at v2.0.

Run with:
    python -m pytest skills/patchbay-research/scripts/test_external_resource_sweep.py -v
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pytest  # noqa: E402

from external_resource_sweep import (  # noqa: E402
    ensure_external_resource_chunks,
    extract_urls_from_chunk,
)
from write_chunk import write_chunks  # noqa: E402


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, chunks: list) -> None:
    path.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _ext_chunks(rows):
    return [r for r in rows if r.get("type") == "external_resource"]


# ---------------------------------------------------------------------------
# Sweep contract — 14 RED cases
# ---------------------------------------------------------------------------

def test_sweep_backfills_missing_external_resource(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "tx-01",
        "type": "text",
        "source": "manual",
        "content": "see https://example.com/article for details",
        "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
    }])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert len(ext) == 1, ext
    assert ext[0]["content"]["url"] == "https://example.com/article"
    assert ext[0]["content"]["citing_chunk_ids"] == ["tx-01"]
    assert ext[0]["tier_used"] is None


def test_sweep_emits_stable_hash_id(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "tx-01",
        "type": "text",
        "source": "manual",
        "content": "see https://example.com/foo",
        "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
    }])
    ensure_external_resource_chunks(str(p))
    rows = _read_jsonl(p)
    foo_ext = [r for r in _ext_chunks(rows) if r["content"]["url"] == "https://example.com/foo"]
    assert len(foo_ext) == 1
    foo_id_first = foo_ext[0]["id"]
    expected_foo_id = "ext-sweep-" + hashlib.sha1(b"https://example.com/foo").hexdigest()[:8]
    assert foo_id_first == expected_foo_id

    # Append a second citing chunk for a DIFFERENT URL and re-sweep.
    rows.append({
        "id": "tx-02",
        "type": "text",
        "source": "manual",
        "content": "see https://example.com/bar",
        "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
    })
    _write_jsonl(p, rows)
    ensure_external_resource_chunks(str(p))
    rows2 = _read_jsonl(p)
    foo_ext2 = [r for r in _ext_chunks(rows2) if r["content"]["url"] == "https://example.com/foo"]
    bar_ext2 = [r for r in _ext_chunks(rows2) if r["content"]["url"] == "https://example.com/bar"]
    assert len(foo_ext2) == 1
    assert len(bar_ext2) == 1
    # foo's id unchanged across runs.
    assert foo_ext2[0]["id"] == foo_id_first
    # bar's id is content-derived sha1 prefix.
    expected_bar_id = "ext-sweep-" + hashlib.sha1(b"https://example.com/bar").hexdigest()[:8]
    assert bar_ext2[0]["id"] == expected_bar_id


def test_sweep_populates_empty_citing_chunk_ids(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [
        {
            "id": "tx-01",
            "type": "text",
            "source": "manual",
            "content": "see https://reddit.com/r/x/comments/abc",
            "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
        },
        {
            "id": "rd-ext-01",
            "type": "external_resource",
            "source": "reddit",
            "content": {
                "resource_type": "article",
                "creator": "",
                "title": "",
                "url": "https://reddit.com/r/x/comments/abc",
                "updated": None,
                "relevance": "",
                "citing_chunk_ids": [],
            },
            "tier_used": 1,
            "provenance": {"url": "https://reddit.com/r/x/comments/abc.json", "scraped_at": "2026-05-17T00:00:00Z"},
        },
    ])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert len(ext) == 1
    assert ext[0]["content"]["citing_chunk_ids"] == ["tx-01"]


def test_sweep_merges_into_nonempty_citing_chunk_ids(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [
        {
            "id": "au-01",
            "type": "artist_usage",
            "source": "equipboard",
            "content": {"artist": "Foo", "verbatim_quote": "see https://youtu.be/abc123XYZ"},
            "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
        },
        {
            "id": "tx-01",
            "type": "text",
            "source": "manual",
            "content": "also https://youtu.be/abc123XYZ",
            "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
        },
        {
            "id": "eb-ext-01",
            "type": "external_resource",
            "source": "equipboard",
            "content": {
                "resource_type": "youtube",
                "creator": "",
                "title": "",
                "url": "https://youtu.be/abc123XYZ",
                "updated": None,
                "relevance": "",
                "citing_chunk_ids": ["au-01"],
            },
            "tier_used": 1,
            "provenance": {"url": "https://youtu.be/abc123XYZ", "scraped_at": "2026-05-17T00:00:00Z"},
        },
    ])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert len(ext) == 1
    assert ext[0]["content"]["citing_chunk_ids"] == sorted(["au-01", "tx-01"])


def test_sweep_canonicalizes_existing_external_resource_urls(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "eb-ext-01",
        "type": "external_resource",
        "source": "equipboard",
        "content": {
            "resource_type": "youtube",
            "creator": "",
            "title": "",
            "url": "https://youtu.be/abc?si=xyz",
            "updated": None,
            "relevance": "",
            "citing_chunk_ids": [],
        },
        "tier_used": 1,
        "provenance": {"url": "https://youtu.be/abc?si=xyz", "scraped_at": "2026-05-17T00:00:00Z"},
    }])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert len(ext) == 1
    assert ext[0]["content"]["url"] == "https://www.youtube.com/watch?v=abc"


def test_sweep_dedupes_by_canonical_url(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [
        {
            "id": "tx-01",
            "type": "text",
            "source": "manual",
            "content": "see https://youtu.be/abc",
            "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
        },
        {
            "id": "tx-02",
            "type": "text",
            "source": "manual",
            "content": "also https://www.youtube.com/watch?v=abc",
            "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
        },
    ])
    ensure_external_resource_chunks(str(p))
    rows = _read_jsonl(p)
    ext = _ext_chunks(rows)
    assert len(ext) == 1, ext
    assert ext[0]["content"]["url"] == "https://www.youtube.com/watch?v=abc"
    assert ext[0]["content"]["citing_chunk_ids"] == sorted(["tx-01", "tx-02"])
    # No dangling references in cross_source_match_candidates (name-based, so
    # naturally safe — assert explicitly per W1).
    ext_id = ext[0]["id"]
    for row in rows:
        cands = row.get("cross_source_match_candidates") or []
        assert ext_id not in cands  # ids never land in this field
        for cand in cands:
            assert not cand.startswith("ext-")  # safety: no ext-* ids leaked


def test_sweep_overrides_existing_resource_type(tmp_path):
    """Reddit emits resource_type='article' for reddit-post URLs; sweep
    overwrites to 'reddit-post' on merge (the sweep classifier is authoritative)."""
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "rd-ext-01",
        "type": "external_resource",
        "source": "reddit",
        "content": {
            "resource_type": "article",   # reddit.py's classification
            "creator": "",
            "title": "",
            "url": "https://reddit.com/r/guitarpedals/comments/abc/def",
            "updated": None,
            "relevance": "",
            "citing_chunk_ids": [],
        },
        "tier_used": 1,
        "provenance": {"url": "https://reddit.com/r/guitarpedals/comments/abc/def", "scraped_at": "2026-05-17T00:00:00Z"},
    }])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert len(ext) == 1
    assert ext[0]["content"]["resource_type"] == "reddit-post"


def test_sweep_emits_null_tier_used(tmp_path):
    """Sweep-emitted external_resource chunks set tier_used = None (JSON null),
    NOT 0 (the locked tier-0 'manual user-paste' escape hatch is a different
    semantic), NOT 'sweep', NOT a missing key."""
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "tx-01",
        "type": "text",
        "source": "manual",
        "content": "see https://example.com/foo",
        "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
    }])
    ensure_external_resource_chunks(str(p))
    # Re-read the file from raw text so we can assert on JSON null specifically.
    raw_lines = [
        l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    ext_lines = [l for l in raw_lines if '"type": "external_resource"' in l or '"type":"external_resource"' in l]
    assert len(ext_lines) == 1
    parsed = json.loads(ext_lines[0])
    assert "tier_used" in parsed
    assert parsed["tier_used"] is None
    # Explicit string check — JSON null serialization in the raw line.
    assert '"tier_used": null' in ext_lines[0] or '"tier_used":null' in ext_lines[0]


def test_sweep_idempotent(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [
        {
            "id": "tx-01",
            "type": "text",
            "source": "manual",
            "content": "see https://youtu.be/abc?si=xyz and https://example.com/article/",
            "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
        },
        {
            "id": "au-01",
            "type": "artist_usage",
            "source": "equipboard",
            "content": {"artist": "Foo", "verbatim_quote": "https://youtu.be/abc"},
            "provenance": {"url": "https://equipboard.com/items/foo", "scraped_at": "2026-05-17T00:00:00Z"},
        },
    ])
    ensure_external_resource_chunks(str(p))
    first = p.read_bytes()
    ensure_external_resource_chunks(str(p))
    second = p.read_bytes()
    assert first == second


def test_sweep_skips_external_resource_self_reference(tmp_path):
    """An external_resource chunk's own .url is NOT a citation target — the
    sweep does not emit a new external_resource pointing at another
    external_resource's URL."""
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [
        {
            "id": "eb-ext-01",
            "type": "external_resource",
            "source": "equipboard",
            "content": {
                "resource_type": "youtube",
                "creator": "",
                "title": "",
                "url": "https://www.youtube.com/watch?v=abc",
                "updated": None,
                "relevance": "",
                "citing_chunk_ids": [],
            },
            "tier_used": 1,
            "provenance": {"url": "https://www.youtube.com/watch?v=abc", "scraped_at": "2026-05-17T00:00:00Z"},
        },
        {
            "id": "eb-ext-02",
            "type": "external_resource",
            "source": "equipboard",
            "content": {
                "resource_type": "youtube",
                "creator": "",
                "title": "",
                "url": "https://www.youtube.com/watch?v=xyz",
                "updated": None,
                "relevance": "",
                "citing_chunk_ids": [],
            },
            "tier_used": 1,
            "provenance": {"url": "https://www.youtube.com/watch?v=xyz", "scraped_at": "2026-05-17T00:00:00Z"},
        },
    ])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    # Only the two existing external_resource chunks should remain — no new
    # ones added (sweep does not extract URLs from external_resource chunks).
    assert len(ext) == 2


def test_sweep_extracts_from_nested_content_dicts(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "au-01",
        "type": "artist_usage",
        "source": "equipboard",
        "content": {
            "artist": "X",
            "verbatim_quote": "Watch https://youtu.be/abc on this rig",
        },
        "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
    }])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert len(ext) == 1
    assert ext[0]["content"]["url"] == "https://www.youtube.com/watch?v=abc"
    assert ext[0]["content"]["citing_chunk_ids"] == ["au-01"]


def test_sweep_extracts_from_provenance_url(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "ms-01",
        "type": "multimodal_segment",
        "source": "youtube",
        "content": {"frame_description": "knob at 2:00"},
        "provenance": {
            "url": "https://www.youtube.com/watch?v=xyz",
            "scraped_at": "2026-05-17T00:00:00Z",
        },
    }])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert len(ext) == 1
    assert ext[0]["content"]["url"] == "https://www.youtube.com/watch?v=xyz"
    assert ext[0]["content"]["citing_chunk_ids"] == ["ms-01"]


def test_sweep_skips_unusable_urls(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(p, [{
        "id": "tx-01",
        "type": "text",
        "source": "manual",
        "content": "see javascript:alert(1) and not-a-url here",
        "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
    }])
    ensure_external_resource_chunks(str(p))
    ext = _ext_chunks(_read_jsonl(p))
    assert ext == []


def test_write_chunks_invokes_sweep(tmp_path):
    """Integration: write_chunks calls the sweep on every append."""
    gear_root = tmp_path
    chunks_path = gear_root / "knowledge" / "chunks.jsonl"
    write_chunks(
        str(chunks_path),
        [{
            "id": "tx-01",
            "type": "text",
            "source": "manual",
            "content": "see https://example.com/article",
            "provenance": {"scraped_at": "2026-05-17T00:00:00Z"},
        }],
        gear_root=str(gear_root),
    )
    rows = _read_jsonl(chunks_path)
    ext = _ext_chunks(rows)
    assert len(ext) == 1
    assert ext[0]["content"]["url"] == "https://example.com/article"
    assert ext[0]["content"]["citing_chunk_ids"] == ["tx-01"]
