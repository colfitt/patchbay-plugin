"""Test suite for verify_resource.py + write_chunks trust= parameter.

Covers CITATION-03 (Plan 04-03): mark a surfaced citation recommendation as
verified — canonicalize URL, dispatch downstream ingestion via url_router,
stamp emitted chunks with trust="high", and atomically update the
external_resource chunk's content.relevance + top-level trust.

Plus the write_chunks `trust=` keyword-only parameter addition (binary-
compatible with all existing 3-positional callers).

Run:
    python -m pytest skills/patchbay-research/scripts/test_verify_resource.py -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from typing import Optional, Tuple

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from write_chunk import write_chunks  # noqa: E402

from verify_resource import (  # noqa: E402
    promote_chunks_to_high_trust,
    verify_resource,
)


VERIFY_PY = HERE / "verify_resource.py"


# ---------------------------------------------------------------------------
# Common helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, chunks: list) -> None:
    path.write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _ext_resource(
    *,
    chunk_id: str,
    url: str,
    citing_chunk_ids: list,
    resource_type: str = "article",
    creator: str = "",
    title: str = "",
    relevance: str = "",
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
            "relevance": relevance,
            "citing_chunk_ids": list(citing_chunk_ids),
        },
        "tier_used": None,
        "provenance": {"url": url, "scraped_at": "2026-05-17T00:00:00Z"},
    }


def _make_fake_module(
    *,
    match_predicate,
    fetch_result,
    parse_chunks,
    record_calls=None,
):
    """Build a fake source-class module exposing the three callables
    url_router.route_url requires.

    Args:
      match_predicate: callable(url) -> bool
      fetch_result:    dict returned by fetch_tier1(url)
      parse_chunks:    list[dict] (deep-copied per call) returned by
                       parse_to_chunks(result, ctx).
      record_calls:    optional dict; if provided, fetch_tier1 + parse_to_chunks
                       append {"fetch": [url, ...], "parse": [ctx, ...]} entries.

    Returns the constructed module.
    """
    mod = types.ModuleType("fake_source_class")

    def _match(u):
        return bool(match_predicate(u))

    def _fetch(u):
        if record_calls is not None:
            record_calls.setdefault("fetch", []).append(u)
        return dict(fetch_result)

    def _parse(result, ctx):
        if record_calls is not None:
            record_calls.setdefault("parse", []).append({
                "result": dict(result),
                "ctx": dict(ctx) if isinstance(ctx, dict) else ctx,
            })
        # Deep-copy each chunk so callers can mutate without leaking back.
        return [json.loads(json.dumps(c)) for c in parse_chunks]

    mod.match_url = _match
    mod.fetch_tier1 = _fetch
    mod.parse_to_chunks = _parse
    return mod


def _gear_layout(tmp_path: Path) -> tuple[Path, Path]:
    """Create a `<tmp>/Brand_Item/knowledge/chunks.jsonl` layout and return
    (gear_root, chunks_path)."""
    gear_root = tmp_path
    item_dir = gear_root / "Brand_Item" / "knowledge"
    item_dir.mkdir(parents=True)
    chunks_path = item_dir / "chunks.jsonl"
    chunks_path.write_text("", encoding="utf-8")
    return gear_root, chunks_path


def _new_chunk(chunk_id: str, source: str, text: str) -> dict:
    return {
        "id": chunk_id,
        "type": "text",
        "source": source,
        "content": {"text": text},
        "tier_used": 1,
        "provenance": {"url": "https://example.com/article",
                       "scraped_at": "2026-05-17T00:00:00Z"},
    }


# ---------------------------------------------------------------------------
# write_chunks trust= parameter (Tests 1-4)
# ---------------------------------------------------------------------------


def test_write_chunks_trust_param_stamps_every_chunk(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    chunk_a = _new_chunk("a-01", "manual", "alpha content")
    chunk_b = _new_chunk("b-02", "manual", "beta content")
    write_chunks(
        str(chunks_path),
        [chunk_a, chunk_b],
        gear_root=str(gear_root),
        trust="high",
    )
    rows = _read_jsonl(chunks_path)
    text_rows = [r for r in rows if r.get("type") == "text"]
    assert len(text_rows) == 2
    for row in text_rows:
        assert row.get("trust") == "high"


def test_write_chunks_trust_default_no_stamp(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    chunk_a = _new_chunk("a-01", "manual", "alpha content")
    write_chunks(str(chunks_path), [chunk_a], gear_root=str(gear_root))
    rows = _read_jsonl(chunks_path)
    text_rows = [r for r in rows if r.get("type") == "text"]
    assert len(text_rows) == 1
    # No trust key on the chunk (or, if pre-set by caller, untouched).
    assert "trust" not in text_rows[0]


def test_write_chunks_trust_empty_string_no_stamp(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    chunk_a = _new_chunk("a-01", "manual", "alpha content")
    write_chunks(
        str(chunks_path),
        [chunk_a],
        gear_root=str(gear_root),
        trust="",
    )
    rows = _read_jsonl(chunks_path)
    text_rows = [r for r in rows if r.get("type") == "text"]
    assert len(text_rows) == 1
    assert "trust" not in text_rows[0]


def test_write_chunks_trust_param_preserves_phase3_caller_behavior(tmp_path):
    # Mirrors review_failures.py L454 + test_core.py L235 invocation shape.
    gear_root, chunks_path = _gear_layout(tmp_path)
    chunk_a = _new_chunk("a-01", "manual", "alpha content")
    result = write_chunks(str(chunks_path), [chunk_a], gear_root=str(gear_root))
    assert result["written"] == 1
    rows = _read_jsonl(chunks_path)
    text_rows = [r for r in rows if r.get("type") == "text"]
    assert len(text_rows) == 1
    assert "trust" not in text_rows[0]


# ---------------------------------------------------------------------------
# verify_resource orchestrator (Tests 5-12)
# ---------------------------------------------------------------------------


def test_verify_resource_dispatches_via_route_url(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://example.com/article"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=url, citing_chunk_ids=[]),
    ])
    calls: dict = {}
    fake = _make_fake_module(
        match_predicate=lambda u: u == url,
        fetch_result={"status": 200, "body": "<html></html>",
                      "headers": {}, "url_attempted": url,
                      "elapsed_ms": 1, "exc": None},
        parse_chunks=[
            _new_chunk("new-01", "article", "fresh content"),
            _new_chunk("new-02", "article", "second fresh"),
        ],
        record_calls=calls,
    )
    result = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        url,
        registry=[fake],
    )
    assert result["ok"] is True
    assert calls.get("fetch") == [url]
    assert len(calls.get("parse") or []) == 1


def test_verify_resource_stamps_new_chunks_trust_high(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://example.com/article"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=url, citing_chunk_ids=[]),
    ])
    fake = _make_fake_module(
        match_predicate=lambda u: u == url,
        fetch_result={"status": 200, "body": "<html></html>",
                      "headers": {}, "url_attempted": url,
                      "elapsed_ms": 1, "exc": None},
        parse_chunks=[
            _new_chunk("new-01", "article", "fresh content"),
            _new_chunk("new-02", "article", "second fresh"),
        ],
    )
    result = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        url,
        registry=[fake],
    )
    assert result["ok"] is True
    assert result["chunks_added"] == 2
    rows = _read_jsonl(chunks_path)
    new_rows = [r for r in rows if r.get("id", "").startswith("new-")]
    assert len(new_rows) == 2
    for row in new_rows:
        assert row.get("trust") == "high"


def test_verify_resource_updates_external_resource_relevance(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://example.com/article"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=url, citing_chunk_ids=[],
                      relevance=""),
    ])
    fake = _make_fake_module(
        match_predicate=lambda u: u == url,
        fetch_result={"status": 200, "body": "<html></html>",
                      "headers": {}, "url_attempted": url,
                      "elapsed_ms": 1, "exc": None},
        parse_chunks=[_new_chunk("new-01", "article", "fresh")],
    )
    verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        url,
        registry=[fake],
    )
    rows = _read_jsonl(chunks_path)
    ext_row = next(r for r in rows if r.get("id") == "ext-01")
    assert ext_row["content"]["relevance"] == "verified"
    # The external_resource chunk had no `trust` key initially — verify the
    # single-segment update_chunk_field call sets it cleanly.
    assert ext_row.get("trust") == "high"


def test_verify_resource_canonicalizes_input_url(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    canonical = "https://www.youtube.com/watch?v=abc"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=canonical, citing_chunk_ids=[]),
    ])
    fake = _make_fake_module(
        match_predicate=lambda u: u == canonical,
        fetch_result={"status": 200, "body": "<html></html>",
                      "headers": {}, "url_attempted": canonical,
                      "elapsed_ms": 1, "exc": None},
        parse_chunks=[_new_chunk("new-01", "youtube", "yt content")],
    )
    # Pass the share-URL form; verify canonicalizes to www.youtube.com/watch?v=abc
    result = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        "https://youtu.be/abc?si=tracking",
        registry=[fake],
    )
    assert result["ok"] is True
    assert result["url"] == canonical
    assert result["external_resource_id"] == "ext-01"


def test_verify_resource_missing_resource_returns_error(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    # chunks.jsonl is empty — no external_resource for the URL.
    fake = _make_fake_module(
        match_predicate=lambda u: True,
        fetch_result={"status": 200, "body": "", "headers": {},
                      "url_attempted": "x", "elapsed_ms": 0, "exc": None},
        parse_chunks=[],
    )
    result = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        "https://example.com/nope",
        registry=[fake],
    )
    assert result["ok"] is False
    assert "--citations" in result["error"]


def test_verify_resource_idempotent_on_reverify(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://example.com/article"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=url, citing_chunk_ids=[]),
    ])
    fake = _make_fake_module(
        match_predicate=lambda u: u == url,
        fetch_result={"status": 200, "body": "<html></html>",
                      "headers": {}, "url_attempted": url,
                      "elapsed_ms": 1, "exc": None},
        parse_chunks=[
            _new_chunk("dup-01", "article", "round one"),
            _new_chunk("dup-02", "article", "round one b"),
        ],
    )
    r1 = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        url,
        registry=[fake],
    )
    assert r1["ok"] is True
    assert r1["chunks_added"] == 2

    # Second invocation: simulate the source class returning two new chunks.
    fake2 = _make_fake_module(
        match_predicate=lambda u: u == url,
        fetch_result={"status": 200, "body": "<html></html>",
                      "headers": {}, "url_attempted": url,
                      "elapsed_ms": 1, "exc": None},
        parse_chunks=[
            _new_chunk("dup-03", "article", "round two"),
            _new_chunk("dup-04", "article", "round two b"),
        ],
    )
    r2 = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        url,
        registry=[fake2],
    )
    assert r2["ok"] is True
    assert r2["chunks_added"] == 2

    rows = _read_jsonl(chunks_path)
    ext_row = next(r for r in rows if r.get("id") == "ext-01")
    assert ext_row["content"]["relevance"] == "verified"
    assert ext_row.get("trust") == "high"
    round_two_rows = [r for r in rows
                      if r.get("id", "").startswith("dup-0")
                      and r.get("id") in ("dup-03", "dup-04")]
    assert len(round_two_rows) == 2
    for row in round_two_rows:
        assert row.get("trust") == "high"


def test_verify_resource_youtube_sentinel_path(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://www.youtube.com/watch?v=abc"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-yt", url=url, citing_chunk_ids=[],
                      resource_type="youtube"),
    ])
    calls: dict = {}
    fake = _make_fake_module(
        match_predicate=lambda u: u == url,
        fetch_result={"status": 0, "body": "", "json": None,
                      "url_attempted": url, "needs_pipeline": True,
                      "headers": {}, "elapsed_ms": 0, "exc": None},
        parse_chunks=[
            _new_chunk("yt-01", "youtube", "multimodal seg one"),
        ],
        record_calls=calls,
    )
    result = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        url,
        registry=[fake],
    )
    assert result["ok"] is True
    # parse_to_chunks must have been called even though status=0 — the
    # needs_pipeline sentinel must NOT be treated as a fetch failure.
    assert len(calls.get("parse") or []) == 1
    rows = _read_jsonl(chunks_path)
    yt_row = next(r for r in rows if r.get("id") == "yt-01")
    assert yt_row.get("trust") == "high"


def test_verify_resource_no_registry_match_returns_error(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://example.com/article"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=url, citing_chunk_ids=[]),
    ])
    # Pass an empty registry — route_url raises ValueError; verify_resource
    # must surface a structured error rather than letting it propagate.
    result = verify_resource(
        chunks_path,
        {"gear_root": str(gear_root), "item": "Brand_Item"},
        url,
        registry=[],
    )
    assert result["ok"] is False
    assert result["error"]


# ---------------------------------------------------------------------------
# CLI surface (Tests 13-15)
# ---------------------------------------------------------------------------


def _write_fake_registry(tmp_path: Path, url: str) -> Path:
    """Write a sibling file `_fake_registry_<id>.py` near verify_resource.py
    that exposes REGISTRY = [fake_module] and records the gear_ctx it was
    invoked with into `<HERE>/_fake_registry_calls.json`.

    Returns the dotted module name to pass via PATCHBAY_VERIFY_REGISTRY_MODULE.
    """
    # Pre-clear the call-record file.
    calls_log = HERE / "_fake_registry_calls.json"
    if calls_log.exists():
        calls_log.unlink()

    module_path = HERE / "_fake_registry_module.py"
    module_path.write_text(
        f"""\
\"\"\"Test fixture: REGISTRY for verify_resource CLI tests.\"\"\"
import json
from pathlib import Path
import types

CALLS_LOG = Path({str(calls_log)!r})


def _record(payload):
    existing = []
    if CALLS_LOG.exists():
        try:
            existing = json.loads(CALLS_LOG.read_text())
        except Exception:
            existing = []
    existing.append(payload)
    CALLS_LOG.write_text(json.dumps(existing))


_TARGET_URL = {url!r}


def _match(u):
    return u == _TARGET_URL


def _fetch(u):
    _record({{"event": "fetch", "url": u}})
    return {{"status": 200, "body": "<html></html>", "headers": {{}},
            "url_attempted": u, "elapsed_ms": 1, "exc": None}}


def _parse(result, ctx):
    _record({{
        "event": "parse",
        "ctx": ctx if isinstance(ctx, dict) else {{}},
    }})
    return [
        {{"id": "fake-01", "type": "text", "source": "article",
         "content": {{"text": "first fake"}}, "tier_used": 1,
         "provenance": {{"url": _TARGET_URL,
                        "scraped_at": "2026-05-17T00:00:00Z"}}}},
        {{"id": "fake-02", "type": "text", "source": "article",
         "content": {{"text": "second fake"}}, "tier_used": 1,
         "provenance": {{"url": _TARGET_URL,
                        "scraped_at": "2026-05-17T00:00:00Z"}}}},
    ]


_mod = types.ModuleType("fake_for_cli")
_mod.match_url = _match
_mod.fetch_tier1 = _fetch
_mod.parse_to_chunks = _parse

REGISTRY = [_mod]
"""
    )
    return calls_log


def _run_verify_cli(chunks_path: Path, *args,
                    env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("PYTHONPATH", str(HERE))
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(VERIFY_PY), str(chunks_path), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_main_verify_exit_zero_on_success(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://example.com/article"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=url, citing_chunk_ids=[]),
    ])
    _write_fake_registry(tmp_path, url)
    cp = _run_verify_cli(
        chunks_path,
        "--gear", "Brand_Item",
        "--url", url,
        "--gear-root", str(gear_root),
        env_extra={"PATCHBAY_VERIFY_REGISTRY_MODULE": "_fake_registry_module"},
    )
    assert cp.returncode == 0, f"stderr: {cp.stderr}\nstdout: {cp.stdout}"
    assert "added" in cp.stdout
    assert "trust=high" in cp.stdout


def test_main_verify_exit_two_on_missing_resource(tmp_path):
    gear_root, chunks_path = _gear_layout(tmp_path)
    # chunks.jsonl exists but has no external_resource for the URL.
    chunks_path.write_text("", encoding="utf-8")
    _write_fake_registry(tmp_path, "https://example.com/article")
    cp = _run_verify_cli(
        chunks_path,
        "--gear", "Brand_Item",
        "--url", "https://example.com/article",
        "--gear-root", str(gear_root),
        env_extra={"PATCHBAY_VERIFY_REGISTRY_MODULE": "_fake_registry_module"},
    )
    assert cp.returncode == 2, f"stderr: {cp.stderr}\nstdout: {cp.stdout}"
    assert "--citations" in cp.stderr


def test_main_verify_default_gear_root_uses_three_parent_levels(tmp_path):
    # Layout: <tmp>/Brand_Item/knowledge/chunks.jsonl
    # Default --gear-root derivation must walk THREE parents up (not two),
    # landing at <tmp> (NOT at <tmp>/Brand_Item).
    gear_root, chunks_path = _gear_layout(tmp_path)
    url = "https://example.com/x"
    _write_jsonl(chunks_path, [
        _ext_resource(chunk_id="ext-01", url=url, citing_chunk_ids=[]),
    ])
    calls_log = _write_fake_registry(tmp_path, url)
    cp = _run_verify_cli(
        chunks_path,
        "--gear", "Brand_Item",
        "--url", url,
        env_extra={"PATCHBAY_VERIFY_REGISTRY_MODULE": "_fake_registry_module"},
    )
    assert cp.returncode == 0, f"stderr: {cp.stderr}\nstdout: {cp.stdout}"
    # The fake recorded gear_ctx — assert the derived gear_root was tmp_path.
    assert calls_log.exists(), "fake registry should have written its calls log"
    events = json.loads(calls_log.read_text())
    parse_events = [e for e in events if e.get("event") == "parse"]
    assert parse_events, f"expected a parse event; got {events!r}"
    derived_gear_root = parse_events[0]["ctx"].get("gear_root")
    assert derived_gear_root is not None
    assert Path(derived_gear_root).resolve() == Path(gear_root).resolve()
    # Crucially NOT the two-parent-up variant.
    assert Path(derived_gear_root).resolve() != (Path(gear_root) / "Brand_Item").resolve()


# ---------------------------------------------------------------------------
# promote_chunks_to_high_trust helper (sanity)
# ---------------------------------------------------------------------------


def test_promote_chunks_to_high_trust_is_pure(tmp_path):
    """Helper must not mutate input; returns a new list with trust='high'."""
    original = [_new_chunk("a", "manual", "x"), _new_chunk("b", "manual", "y")]
    out = promote_chunks_to_high_trust(original)
    assert all(c.get("trust") == "high" for c in out)
    # Input untouched.
    assert all("trust" not in c for c in original)
