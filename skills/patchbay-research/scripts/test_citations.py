"""Test suite for citations.py — citation-recommendation aggregator + CLI.

Covers CITATION-02 (Plan 04-02): aggregate external_resource chunks by
canonical URL, apply N-threshold over DISTINCT citing-chunk sources (not raw
citing_chunk_ids length), and emit either markdown (default) or JSON to
stdout. 20 cases locked at v2.0.

Run with:
    python -m pytest skills/patchbay-research/scripts/test_citations.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from citations import (  # noqa: E402
    Recommendation,
    aggregate_citations,
    format_recommendations_markdown,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

CITATIONS_PY = HERE / "citations.py"


def _write_jsonl(path: Path, chunks: list) -> None:
    path.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks),
        encoding="utf-8",
    )


def _ext_resource(
    *,
    chunk_id: str,
    url: str,
    citing_chunk_ids: list,
    resource_type: str = "youtube",
    creator: str = "",
    title: str = "",
    source: str = "sweep",
) -> dict:
    return {
        "id": chunk_id,
        "type": "external_resource",
        "source": source,
        "content": {
            "resource_type": resource_type,
            "creator": creator,
            "title": title,
            "url": url,
            "updated": None,
            "relevance": "",
            "citing_chunk_ids": citing_chunk_ids,
        },
        "tier_used": None,
        "provenance": {"url": url, "scraped_at": "2026-05-17T00:00:00Z"},
    }


def _text_chunk(
    *,
    chunk_id: str,
    source: str,
    text: str = "",
) -> dict:
    return {
        "id": chunk_id,
        "type": "text",
        "source": source,
        "content": {"text": text or f"a quick mention of https://www.youtube.com/watch?v=abc here"},
        "tier_used": 1,
        "provenance": {"url": "https://example.invalid/", "scraped_at": "2026-05-17T00:00:00Z"},
    }


# ---------------------------------------------------------------------------
# aggregate_citations
# ---------------------------------------------------------------------------


def test_aggregate_returns_empty_for_empty_jsonl(tmp_path):
    p = tmp_path / "chunks.jsonl"
    p.write_text("", encoding="utf-8")
    assert aggregate_citations(p, threshold=2) == []


def test_aggregate_returns_empty_when_no_ext_resource_crosses_threshold(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["tx-01"],
            ),
            _text_chunk(chunk_id="tx-01", source="manual",
                        text="see https://www.youtube.com/watch?v=abc"),
        ],
    )
    assert aggregate_citations(p, threshold=2) == []


def test_aggregate_counts_distinct_sources_not_raw_ids(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01", "rd-02"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit",
                        text="https://www.youtube.com/watch?v=abc"),
            _text_chunk(chunk_id="rd-02", source="reddit",
                        text="https://www.youtube.com/watch?v=abc"),
        ],
    )
    assert aggregate_citations(p, threshold=2) == []


def test_aggregate_surfaces_when_distinct_sources_meets_threshold(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01", "eb-01"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit",
                        text="great review at https://www.youtube.com/watch?v=abc"),
            _text_chunk(chunk_id="eb-01", source="equipboard",
                        text="https://www.youtube.com/watch?v=abc demo"),
        ],
    )
    recs = aggregate_citations(p, threshold=2)
    assert len(recs) == 1
    rec = recs[0]
    assert isinstance(rec, Recommendation)
    assert rec.independent_source_count == 2
    assert rec.canonical_url == "https://www.youtube.com/watch?v=abc"


def test_aggregate_includes_excerpts(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01", "eb-01"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit",
                        text="great review at https://www.youtube.com/watch?v=abc thanks"),
            _text_chunk(chunk_id="eb-01", source="equipboard",
                        text="https://www.youtube.com/watch?v=abc demo video"),
        ],
    )
    recs = aggregate_citations(p, threshold=2)
    assert len(recs) == 1
    for cc in recs[0].citing_chunks:
        assert "excerpt" in cc
        assert len(cc["excerpt"]) <= 100  # ~80 plus optional truncation markers


def test_aggregate_filter_url_canonicalizes_input(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01", "eb-01"],
            ),
            _ext_resource(
                chunk_id="ext-002",
                url="https://www.youtube.com/watch?v=zzz",
                citing_chunk_ids=["rd-02", "eb-02"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit",
                        text="https://www.youtube.com/watch?v=abc"),
            _text_chunk(chunk_id="eb-01", source="equipboard",
                        text="https://www.youtube.com/watch?v=abc"),
            _text_chunk(chunk_id="rd-02", source="reddit",
                        text="https://www.youtube.com/watch?v=zzz"),
            _text_chunk(chunk_id="eb-02", source="equipboard",
                        text="https://www.youtube.com/watch?v=zzz"),
        ],
    )
    # youtu.be short form with tracking param should canonicalize to the
    # watch?v=abc form and match only ext-001.
    recs = aggregate_citations(p, threshold=2, filter_url="https://youtu.be/abc?si=xyz")
    assert len(recs) == 1
    assert recs[0].canonical_url == "https://www.youtube.com/watch?v=abc"


def test_aggregate_filter_url_no_match(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01", "eb-01"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit"),
            _text_chunk(chunk_id="eb-01", source="equipboard"),
        ],
    )
    recs = aggregate_citations(p, threshold=2, filter_url="https://example.com/different")
    assert recs == []


def test_aggregate_threshold_one_returns_all(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01"],
            ),
            _ext_resource(
                chunk_id="ext-002",
                url="https://www.youtube.com/watch?v=zzz",
                citing_chunk_ids=["eb-01"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit"),
            _text_chunk(chunk_id="eb-01", source="equipboard"),
        ],
    )
    recs = aggregate_citations(p, threshold=1)
    assert len(recs) == 2


def test_aggregate_skips_external_resource_with_no_resolvable_citing_chunks(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["nonexistent-id"],
            ),
        ],
    )
    # threshold=1 — the citing id is not resolvable, so the ext_resource is filtered out.
    assert aggregate_citations(p, threshold=1) == []


def test_aggregate_ignores_external_resource_citing_external_resource(tmp_path):
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["ext-002", "rd-01"],
            ),
            _ext_resource(
                chunk_id="ext-002",
                url="https://www.youtube.com/watch?v=zzz",
                citing_chunk_ids=[],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit"),
        ],
    )
    # Only one resolvable, non-external_resource citing chunk → 1 distinct source.
    recs = aggregate_citations(p, threshold=2)
    assert recs == []
    recs1 = aggregate_citations(p, threshold=1)
    assert len(recs1) == 1
    assert recs1[0].independent_source_count == 1


# ---------------------------------------------------------------------------
# format_recommendations_markdown
# ---------------------------------------------------------------------------


def _mkrec(url, count, sources=None, citing=None):
    if sources is None:
        sources = ["reddit", "equipboard"][:count]
    if citing is None:
        citing = [
            {"id": f"c-{i:02d}", "source": sources[i % len(sources)],
             "excerpt": f"excerpt {i}"}
            for i in range(count)
        ]
    return Recommendation(
        canonical_url=url,
        resource_type="youtube",
        creator="",
        title="",
        independent_source_count=count,
        citing_chunks=citing,
        external_resource_chunk_id=f"ext-{url[-3:]}",
    )


def test_format_includes_threshold_in_header():
    rec = _mkrec("https://www.youtube.com/watch?v=abc", 2)
    out = format_recommendations_markdown([rec], gear="Test Gear", threshold=2)
    assert "threshold N=2" in out


def test_format_empty_recommendations_message():
    out = format_recommendations_markdown([], gear="Test Gear", threshold=2)
    assert "No citation recommendations at threshold N=" in out
    assert "Test Gear" in out
    # Per W3: do NOT misdirect user back to /patchbay:research.
    assert "run /patchbay:research" not in out


def test_format_lists_citing_chunks_with_source_prefix():
    rec = _mkrec("https://www.youtube.com/watch?v=abc", 2)
    out = format_recommendations_markdown([rec], gear="Test", threshold=2)
    # Every citing-chunk line should be prefixed with `- [<source>]` somewhere
    citing_lines = [ln for ln in out.splitlines() if ln.strip().startswith("- [")]
    assert len(citing_lines) >= 2
    for ln in citing_lines:
        assert ln.lstrip().startswith("- [")


def test_format_marks_canonical_url_as_first_line_of_each_recommendation():
    rec = _mkrec("https://www.youtube.com/watch?v=abc", 2)
    out = format_recommendations_markdown([rec], gear="Test", threshold=2)
    # The canonical URL appears in a heading line that starts with `## `.
    heading_lines = [ln for ln in out.splitlines() if ln.startswith("## ")]
    assert any("https://www.youtube.com/watch?v=abc" in ln for ln in heading_lines)


def test_format_orders_recommendations_by_source_count_desc():
    rec2 = _mkrec("https://www.youtube.com/watch?v=zzz", 2)
    rec3 = Recommendation(
        canonical_url="https://www.youtube.com/watch?v=aaa",
        resource_type="youtube",
        creator="",
        title="",
        independent_source_count=3,
        citing_chunks=[
            {"id": "c1", "source": "reddit", "excerpt": "x"},
            {"id": "c2", "source": "equipboard", "excerpt": "y"},
            {"id": "c3", "source": "youtube", "excerpt": "z"},
        ],
        external_resource_chunk_id="ext-aaa",
    )
    out = format_recommendations_markdown([rec2, rec3], gear="Test", threshold=2)
    idx3 = out.find("https://www.youtube.com/watch?v=aaa")
    idx2 = out.find("https://www.youtube.com/watch?v=zzz")
    assert idx3 != -1 and idx2 != -1
    assert idx3 < idx2  # the 3-source rec appears first


# ---------------------------------------------------------------------------
# CLI (subprocess)
# ---------------------------------------------------------------------------


def _seed_two_source(tmp_path: Path) -> Path:
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01", "eb-01"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit",
                        text="https://www.youtube.com/watch?v=abc"),
            _text_chunk(chunk_id="eb-01", source="equipboard",
                        text="https://www.youtube.com/watch?v=abc"),
        ],
    )
    return p


def _run_cli(chunks_path: Path, *args, env_extra=None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Strip any pre-existing override so default-threshold tests are clean.
    env.pop("PATCHBAY_CITATION_THRESHOLD", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(CITATIONS_PY), str(chunks_path), "--gear", "Test Gear", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_main_default_threshold_is_two(tmp_path):
    p = _seed_two_source(tmp_path)
    cp = _run_cli(p)
    assert cp.returncode == 0, cp.stderr
    assert "N=2" in cp.stdout


def test_main_threshold_flag_overrides(tmp_path):
    p = _seed_two_source(tmp_path)
    cp = _run_cli(p, "--threshold", "3")
    assert cp.returncode == 0, cp.stderr
    assert "N=3" in cp.stdout


def test_main_threshold_env_var(tmp_path):
    p = _seed_two_source(tmp_path)
    cp = _run_cli(p, env_extra={"PATCHBAY_CITATION_THRESHOLD": "5"})
    assert cp.returncode == 0, cp.stderr
    assert "N=5" in cp.stdout


def test_main_json_flag_emits_valid_json(tmp_path):
    p = _seed_two_source(tmp_path)
    cp = _run_cli(p, "--json", "--threshold", "1")
    assert cp.returncode == 0, cp.stderr
    parsed = json.loads(cp.stdout)
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    rec = parsed[0]
    for key in (
        "canonical_url",
        "resource_type",
        "creator",
        "title",
        "independent_source_count",
        "citing_chunks",
        "external_resource_chunk_id",
    ):
        assert key in rec


def test_main_exit_zero_on_no_results(tmp_path):
    # Threshold=2 against a chunks.jsonl with only single-source citations.
    p = tmp_path / "chunks.jsonl"
    _write_jsonl(
        p,
        [
            _ext_resource(
                chunk_id="ext-001",
                url="https://www.youtube.com/watch?v=abc",
                citing_chunk_ids=["rd-01"],
            ),
            _text_chunk(chunk_id="rd-01", source="reddit"),
        ],
    )
    cp = _run_cli(p)
    assert cp.returncode == 0, cp.stderr
    assert "No citation recommendations at threshold N=2" in cp.stdout
