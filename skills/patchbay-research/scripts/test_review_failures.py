"""Test suite for the `/patchbay:research --review-failures` flow (Plan 05).

Covers the 12 named acceptance tests from the plan:

  1. test_load_failures_filters_resolved_urls
  2. test_load_failures_skips_malformed_lines
  3. test_append_resolution_writes_resolution_record
  4. test_precheck_returns_false_when_empty
  5. test_precheck_returns_true_when_browsers_listed
  6. test_review_choice_tier2_extension_missing_does_not_fallback
  7. test_review_choice_tier2_success_writes_chunks
  8. test_review_choice_tier3_uses_argv_subprocess
  9. test_review_choice_paste_routes_through_parser
 10. test_review_choice_skip_appends_resolution
 11. test_no_auto_fallback_after_tier2_fetch_failure
 12. test_cross_source_match_candidates_emerges_after_escalation

The `prompt_user` callable and the `mcp_tools` dict are injected so the suite
can exercise the full flow with no real Chrome extension and no real MCP
surface present. Subprocess in tier3_vision is monkeypatched.

Run with:

    python3 -m pytest skills/patchbay-research/scripts/test_review_failures.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Make sibling scripts importable regardless of cwd. Also add the package
# root so `source_classes` resolves the same way as in test_reddit /
# test_equipboard / test_youtube.
HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(RESEARCH_ROOT))

import review_failures  # noqa: E402
import tier2_chrome  # noqa: E402
import tier3_vision  # noqa: E402
from log_failure import log_failure  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_failure_line(failures_log_path: Path, **fields) -> None:
    """Append a single failure JSONL line directly (bypasses log_failure
    classification). Used to seed test fixtures with arbitrary content."""
    default = {
        "timestamp": "2026-05-16T00:00:00Z",
        "url": "https://example.com/foo",
        "tier_attempted": 1,
        "http_status": 403,
        "reason": "cloudflare-block",
        "reason_detail": "Server returned 403.",
        "suggested_escalation": 2,
        "last_attempted": "2026-05-16T00:00:00Z",
        "retry_count": 1,
    }
    default.update(fields)
    failures_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(failures_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(default) + "\n")


def _write_raw_line(failures_log_path: Path, raw_text: str) -> None:
    """Append a raw line (may be malformed) without JSON validation."""
    failures_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(failures_log_path, "a", encoding="utf-8") as f:
        f.write(raw_text + ("\n" if not raw_text.endswith("\n") else ""))


def _stub_mcp_tools(**overrides):
    """Default MCP-tool stubs that no-op or raise unless overridden."""
    def _missing(name):
        def _fn(*args, **kwargs):
            raise AssertionError(f"MCP tool {name!r} was called unexpectedly.")
        return _fn

    tools = {
        "list_connected_browsers": _missing("list_connected_browsers"),
        "select_browser": _missing("select_browser"),
        "tabs_context_mcp": _missing("tabs_context_mcp"),
        "browser_batch": _missing("browser_batch"),
        "get_page_text": _missing("get_page_text"),
        "request_access": _missing("request_access"),
        "screenshot": _missing("screenshot"),
    }
    tools.update(overrides)
    return tools


# Fake gear context. Equipboard parser will use `item` for from_gear; the
# Reddit parser only consumes the dict shape (gear_ctx is permissive).
GEAR_CTX = {
    "brand": "Chase Bliss Audio",
    "item": "Clean",
    "scraped_at": "2026-05-16T00:00:00Z",
}


# ---------------------------------------------------------------------------
# Test 1
# ---------------------------------------------------------------------------

def test_load_failures_filters_resolved_urls(tmp_path):
    """A failure entry that has a later resolution record for the same URL
    must NOT be returned by load_failures."""
    log = tmp_path / "failures.log"
    _write_failure_line(
        log,
        url="https://equipboard.com/items/foo",
        timestamp="2026-05-16T00:00:00Z",
    )
    # Append a resolution record for the SAME url.
    review_failures.append_resolution(
        str(log),
        url="https://equipboard.com/items/foo",
        tier_used=0,
        outcome="success",
        chunks_written=3,
    )

    out = review_failures.load_failures(str(log))
    assert out == [], (
        "load_failures should filter out entries with a later resolution record "
        f"for the same URL, got: {out!r}"
    )


# ---------------------------------------------------------------------------
# Test 2
# ---------------------------------------------------------------------------

def test_load_failures_skips_malformed_lines(tmp_path, capsys):
    """A malformed JSON line is skipped with a printed warning; lines around
    it are returned intact."""
    log = tmp_path / "failures.log"
    _write_failure_line(log, url="https://reddit.com/r/x/comments/aaa")
    _write_raw_line(log, "this is not json {")
    _write_failure_line(log, url="https://reddit.com/r/x/comments/bbb")

    out = review_failures.load_failures(str(log))
    captured = capsys.readouterr()
    urls = [entry["url"] for entry in out]
    assert urls == [
        "https://reddit.com/r/x/comments/aaa",
        "https://reddit.com/r/x/comments/bbb",
    ], f"Expected both valid lines, got {urls!r}"
    # Warning must be visible (covers `warning`/`warn`/`malformed`/`skip`).
    assert ("warn" in captured.out.lower() or "skip" in captured.out.lower()
            or "malformed" in captured.out.lower()), (
        "Expected a printed warning about a malformed line; captured: "
        f"{captured.out!r}"
    )


# ---------------------------------------------------------------------------
# Test 3
# ---------------------------------------------------------------------------

def test_append_resolution_writes_resolution_record(tmp_path):
    """append_resolution writes a one-line JSON record with type=resolution."""
    log = tmp_path / "failures.log"
    review_failures.append_resolution(
        str(log),
        url="https://example.com/foo",
        tier_used=2,
        outcome="success",
        chunks_written=5,
    )

    last_line = log.read_text(encoding="utf-8").splitlines()[-1]
    record = json.loads(last_line)
    assert record["type"] == "resolution"
    assert record["url"] == "https://example.com/foo"
    assert record["tier_used"] == 2
    assert record["outcome"] == "success"
    assert record["chunks_written"] == 5
    assert "resolved_at" in record and record["resolved_at"].endswith("Z")


# ---------------------------------------------------------------------------
# Test 4
# ---------------------------------------------------------------------------

def test_precheck_returns_false_when_empty(capsys):
    """precheck returns False when list_connected_browsers returns []."""
    tools = _stub_mcp_tools(list_connected_browsers=lambda: [])
    assert tier2_chrome.precheck_chrome_extension(tools) is False
    captured = capsys.readouterr()
    # Must print install instructions.
    assert "extension" in captured.out.lower()
    assert "install" in captured.out.lower()


# ---------------------------------------------------------------------------
# Test 5
# ---------------------------------------------------------------------------

def test_precheck_returns_true_when_browsers_listed():
    """precheck returns True when list_connected_browsers returns a non-empty
    list."""
    tools = _stub_mcp_tools(
        list_connected_browsers=lambda: [{"deviceId": "abc"}]
    )
    assert tier2_chrome.precheck_chrome_extension(tools) is True


# ---------------------------------------------------------------------------
# Test 6
# ---------------------------------------------------------------------------

def test_review_choice_tier2_extension_missing_does_not_fallback(
    tmp_path, monkeypatch
):
    """User picks tier-2 but precheck returns False; outcome must be
    extension-missing AND fetch_tier2/fetch_tier3 must NOT be called."""
    log = tmp_path / "failures.log"
    chunks_path = tmp_path / "chunks.jsonl"
    _write_failure_line(log, url="https://equipboard.com/items/clean")

    tier2_called = []
    tier3_called = []

    def _fake_fetch_tier2(url, mcp_tools):
        tier2_called.append(url)
        return {"status": 200, "body": "", "tier": 2}

    def _fake_fetch_tier3(url, mcp_tools, prompt_user):
        tier3_called.append(url)
        return {"status": 200, "body": "", "tier": 3}

    monkeypatch.setattr(tier2_chrome, "fetch_tier2", _fake_fetch_tier2)
    monkeypatch.setattr(tier3_vision, "fetch_tier3", _fake_fetch_tier3)

    tools = _stub_mcp_tools(list_connected_browsers=lambda: [])

    result = review_failures.review_failures(
        failures_log_path=str(log),
        chunks_jsonl_path=str(chunks_path),
        gear_ctx=GEAR_CTX,
        prompt_user=lambda entry: "tier-2",
        mcp_tools=tools,
    )

    assert tier2_called == [], "fetch_tier2 must NOT be called when precheck fails."
    assert tier3_called == [], "fetch_tier3 must NEVER be auto-invoked (no fallback)."
    # A resolution with outcome extension-missing was appended.
    lines = log.read_text(encoding="utf-8").splitlines()
    resolutions = [json.loads(ln) for ln in lines if '"type": "resolution"' in ln]
    assert any(r["outcome"] == "extension-missing" for r in resolutions), (
        f"Expected an extension-missing resolution, got: {resolutions!r}"
    )
    assert result["extension_missing"] >= 1


# ---------------------------------------------------------------------------
# Test 7
# ---------------------------------------------------------------------------

# Minimal Reddit response body — two-listing JSON shape. The Reddit source
# class fetches with `?.json`, so any tier-2 reply MUST also be a JSON
# string. We craft a tiny but valid listing to drive parse_to_chunks.
_REDDIT_TIER2_BODY = json.dumps([
    {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "tier2post",
                        "title": "Real-world Chase Bliss Clean discussion",
                        "selftext": "Has anyone A/B tested this against the Cali76?",
                        "permalink": "/r/guitarpedals/comments/tier2post/clean/",
                        "url": "https://reddit.com/r/guitarpedals/comments/tier2post/clean/",
                        "author": "tester",
                        "ups": 12,
                        "created_utc": 1715823600,
                    },
                }
            ]
        }
    },
    {
        "data": {
            "children": [
                {
                    "kind": "t1",
                    "data": {
                        "id": "c1",
                        "body": "Yes — Clean is more open. Cali76 squashes harder.",
                        "author": "user1",
                        "ups": 8,
                        "created_utc": 1715827200,
                    },
                }
            ]
        }
    },
])


def test_review_choice_tier2_success_writes_chunks(tmp_path, monkeypatch):
    """User picks tier-2, precheck passes, fetch_tier2 returns a Reddit-shaped
    body; chunks must be written and resolution outcome=success, tier_used=2."""
    log = tmp_path / "failures.log"
    chunks_path = tmp_path / "chunks.jsonl"
    target_url = "https://www.reddit.com/r/guitarpedals/comments/tier2post/clean/"
    _write_failure_line(
        log,
        url=target_url,
        reason="cloudflare-block",
        suggested_escalation=2,
    )

    def _fake_fetch_tier2(url, mcp_tools):
        return {
            "status": 200,
            "body": _REDDIT_TIER2_BODY,
            "json": json.loads(_REDDIT_TIER2_BODY),
            "url_attempted": url,
            "tier": 2,
        }

    monkeypatch.setattr(tier2_chrome, "fetch_tier2", _fake_fetch_tier2)
    tools = _stub_mcp_tools(
        list_connected_browsers=lambda: [{"deviceId": "abc"}]
    )

    result = review_failures.review_failures(
        failures_log_path=str(log),
        chunks_jsonl_path=str(chunks_path),
        gear_ctx=GEAR_CTX,
        prompt_user=lambda entry: "tier-2",
        mcp_tools=tools,
    )

    # Chunks file must exist + carry at least one chunk with tier_used == 2.
    assert chunks_path.exists(), "chunks.jsonl was not written."
    chunks = [
        json.loads(ln) for ln in chunks_path.read_text("utf-8").splitlines() if ln
    ]
    assert chunks, "No chunks were written."
    assert any(c.get("tier_used") == 2 for c in chunks), (
        f"Expected at least one chunk with tier_used == 2; got: "
        f"{[c.get('tier_used') for c in chunks]!r}"
    )
    # Resolution record present, success, tier_used == 2.
    resolutions = [
        json.loads(ln) for ln in log.read_text("utf-8").splitlines()
        if '"type": "resolution"' in ln
    ]
    matched = [r for r in resolutions if r["url"] == target_url]
    assert matched, f"No resolution for {target_url}; got: {resolutions!r}"
    assert matched[-1]["outcome"] == "success"
    assert matched[-1]["tier_used"] == 2
    assert matched[-1]["chunks_written"] >= 1
    assert result["escalated"] >= 1


# ---------------------------------------------------------------------------
# Test 8
# ---------------------------------------------------------------------------

def test_review_choice_tier3_uses_argv_subprocess(tmp_path, monkeypatch):
    """User picks tier-3 — the `open` subprocess call must use shell=False
    and pass the URL as a single argv element."""
    log = tmp_path / "failures.log"
    chunks_path = tmp_path / "chunks.jsonl"
    target_url = "https://example.com/article-about-Chase-Bliss"
    _write_failure_line(log, url=target_url, suggested_escalation=3)

    # Capture EVERY subprocess.run call. The URL may route to the generic
    # fallback source class (currently youtube), which may invoke yt-dlp /
    # ffmpeg through subprocess.run during parse_to_chunks. The test cares
    # about the `open` call specifically — we filter for it after the fact.
    all_calls = []

    def _fake_run(argv, *args, **kwargs):
        all_calls.append({"argv": argv, "kwargs": kwargs})

        class _Done:
            returncode = 0
            stdout = b""
            stderr = b""

        return _Done()

    monkeypatch.setattr(subprocess, "run", _fake_run)
    if hasattr(tier3_vision, "subprocess"):
        monkeypatch.setattr(tier3_vision.subprocess, "run", _fake_run)

    tools = _stub_mcp_tools(
        request_access=lambda apps, reason=None: {"granted": apps},
        screenshot=lambda **kw: {"path": str(tmp_path / "shot.png")},
    )

    review_failures.review_failures(
        failures_log_path=str(log),
        chunks_jsonl_path=str(chunks_path),
        gear_ctx=GEAR_CTX,
        # tier-3 may prompt twice (action + scroll); always answer "tier-3" first,
        # and fall through to a benign response for any subsequent prompt.
        prompt_user=lambda entry: "tier-3" if isinstance(entry, dict) else "",
        mcp_tools=tools,
    )

    # Find the `open` call among all subprocess.run invocations.
    open_calls = [
        c for c in all_calls
        if isinstance(c["argv"], (list, tuple)) and c["argv"] and c["argv"][0] == "open"
    ]
    assert open_calls, (
        f"tier-3 path must invoke `open` via subprocess.run; got argv[0] values: "
        f"{[c['argv'][0] if c['argv'] else None for c in all_calls]!r}"
    )
    call = open_calls[0]
    argv = call["argv"]
    assert isinstance(argv, (list, tuple)), (
        "argv must be a list/tuple (shell=False idiom); "
        f"got {type(argv).__name__}: {argv!r}"
    )
    assert target_url in argv, (
        f"URL must be passed as a single argv element; argv={argv!r}"
    )
    # The URL must NOT be interpolated into another argv element.
    interpolated = [a for a in argv if a != target_url and target_url in a]
    assert not interpolated, (
        f"URL appears interpolated into another argv element: {interpolated!r}"
    )
    kwargs = call["kwargs"] or {}
    assert kwargs.get("shell", False) is False, (
        f"subprocess.run was called with shell=True: {kwargs!r}"
    )
    # Belt-and-suspenders: NO call in this test should have shell=True.
    for c in all_calls:
        assert (c["kwargs"] or {}).get("shell", False) is False, (
            f"shell=True detected in a subprocess.run call: {c!r}"
        )


# ---------------------------------------------------------------------------
# Test 9
# ---------------------------------------------------------------------------

_EQUIPBOARD_FIXTURE = (
    RESEARCH_ROOT / "scripts" / "fixtures" / "equipboard_sample.html"
).read_text("utf-8")


def test_review_choice_paste_routes_through_parser(tmp_path):
    """User picks paste, supplies a fake DOM body that equipboard can parse;
    chunks are written and resolution tier_used == 0."""
    log = tmp_path / "failures.log"
    chunks_path = tmp_path / "chunks.jsonl"
    target_url = "https://equipboard.com/items/chase-bliss-clean"
    _write_failure_line(log, url=target_url, suggested_escalation="manual-paste")

    def _prompt(arg):
        # First call: action selection for the failure entry. Subsequent
        # call(s): the pasted body. We can detect by type — entries are
        # dicts; the paste-prompt call passes a string sentinel.
        if isinstance(arg, dict):
            return "paste"
        # Any other call: the paste prompt.
        return _EQUIPBOARD_FIXTURE

    tools = _stub_mcp_tools()  # No MCP tools should be invoked for paste path.

    result = review_failures.review_failures(
        failures_log_path=str(log),
        chunks_jsonl_path=str(chunks_path),
        gear_ctx=GEAR_CTX,
        prompt_user=_prompt,
        mcp_tools=tools,
    )

    chunks = [
        json.loads(ln) for ln in chunks_path.read_text("utf-8").splitlines() if ln
    ]
    assert chunks, "Expected at least one chunk written via the paste path."
    assert any(c.get("tier_used") == 0 for c in chunks), (
        f"Expected at least one chunk with tier_used == 0; got: "
        f"{[c.get('tier_used') for c in chunks]!r}"
    )
    resolutions = [
        json.loads(ln) for ln in log.read_text("utf-8").splitlines()
        if '"type": "resolution"' in ln
    ]
    assert resolutions, f"No resolution record; lines={log.read_text('utf-8')!r}"
    assert resolutions[-1]["tier_used"] == 0
    assert resolutions[-1]["outcome"] == "success"
    assert result["escalated"] >= 1


# ---------------------------------------------------------------------------
# Test 10
# ---------------------------------------------------------------------------

def test_review_choice_skip_appends_resolution(tmp_path):
    """User picks skip — resolution outcome == user-skipped."""
    log = tmp_path / "failures.log"
    chunks_path = tmp_path / "chunks.jsonl"
    _write_failure_line(log, url="https://example.com/dead")

    result = review_failures.review_failures(
        failures_log_path=str(log),
        chunks_jsonl_path=str(chunks_path),
        gear_ctx=GEAR_CTX,
        prompt_user=lambda entry: "skip",
        mcp_tools=_stub_mcp_tools(),
    )

    resolutions = [
        json.loads(ln) for ln in log.read_text("utf-8").splitlines()
        if '"type": "resolution"' in ln
    ]
    assert resolutions, "No resolution record was written for skip path."
    assert resolutions[-1]["outcome"] == "user-skipped"
    assert resolutions[-1]["tier_used"] is None
    assert resolutions[-1]["chunks_written"] == 0
    assert result["skipped"] >= 1


# ---------------------------------------------------------------------------
# Test 11
# ---------------------------------------------------------------------------

def test_no_auto_fallback_after_tier2_fetch_failure(tmp_path, monkeypatch):
    """tier-2 fetch raises; outcome=tier-error AND tier-3 is NOT auto-invoked."""
    log = tmp_path / "failures.log"
    chunks_path = tmp_path / "chunks.jsonl"
    target_url = "https://equipboard.com/items/error-prone"
    _write_failure_line(log, url=target_url, suggested_escalation=2)

    def _fake_fetch_tier2(url, mcp_tools):
        raise RuntimeError("tier-2 explosion")

    tier3_called = []

    def _fake_fetch_tier3(url, mcp_tools, prompt_user):
        tier3_called.append(url)
        return {"status": 200, "body": "", "tier": 3}

    monkeypatch.setattr(tier2_chrome, "fetch_tier2", _fake_fetch_tier2)
    monkeypatch.setattr(tier3_vision, "fetch_tier3", _fake_fetch_tier3)

    tools = _stub_mcp_tools(
        list_connected_browsers=lambda: [{"deviceId": "abc"}]
    )

    review_failures.review_failures(
        failures_log_path=str(log),
        chunks_jsonl_path=str(chunks_path),
        gear_ctx=GEAR_CTX,
        prompt_user=lambda entry: "tier-2",
        mcp_tools=tools,
    )

    assert tier3_called == [], (
        "fetch_tier3 must NEVER be auto-invoked after a tier-2 failure (no "
        f"auto-fallback); got calls: {tier3_called!r}"
    )
    resolutions = [
        json.loads(ln) for ln in log.read_text("utf-8").splitlines()
        if '"type": "resolution"' in ln
    ]
    assert resolutions and resolutions[-1]["outcome"] == "tier-error", (
        f"Expected outcome=tier-error; got resolutions={resolutions!r}"
    )


# ---------------------------------------------------------------------------
# Test 12
# ---------------------------------------------------------------------------

def test_cross_source_match_candidates_emerges_after_escalation(
    tmp_path, monkeypatch
):
    """Pre-seed chunks.jsonl with a chunk mentioning 'Rhett Shull'; run an
    escalation that produces another chunk also mentioning him; the new
    chunk MUST have 'Rhett Shull' in cross_source_match_candidates."""
    log = tmp_path / "failures.log"
    chunks_path = tmp_path / "chunks.jsonl"
    target_url = "https://www.reddit.com/r/guitarpedals/comments/seedXY/clean/"

    # Seed: one prior chunk mentioning Rhett Shull (manual ingest shape).
    with open(chunks_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "id": "manual-1",
            "type": "text",
            "source": "manual",
            "content": (
                "Recommended in Rhett Shull's pedalboard tour video about "
                "compression."
            ),
            "provenance": {"scraped_at": "2026-05-15T00:00:00Z"},
            "tier_used": 0,
        }) + "\n")

    _write_failure_line(log, url=target_url, suggested_escalation=2)

    # Escalation body: a Reddit listing whose OP selftext mentions Rhett Shull.
    body = json.dumps([
        {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "seedXY",
                            "title": "Anyone heard Rhett Shull on Chase Bliss Clean?",
                            "selftext": (
                                "Rhett Shull is the reason I'm looking at this "
                                "compressor."
                            ),
                            "permalink": (
                                "/r/guitarpedals/comments/seedXY/clean/"
                            ),
                            "url": target_url,
                            "author": "tester",
                            "ups": 5,
                            "created_utc": 1715823600,
                        },
                    }
                ]
            }
        },
        {"data": {"children": []}},
    ])

    def _fake_fetch_tier2(url, mcp_tools):
        return {
            "status": 200,
            "body": body,
            "json": json.loads(body),
            "url_attempted": url,
            "tier": 2,
        }

    monkeypatch.setattr(tier2_chrome, "fetch_tier2", _fake_fetch_tier2)
    tools = _stub_mcp_tools(
        list_connected_browsers=lambda: [{"deviceId": "abc"}]
    )

    review_failures.review_failures(
        failures_log_path=str(log),
        chunks_jsonl_path=str(chunks_path),
        gear_ctx=GEAR_CTX,
        prompt_user=lambda entry: "tier-2",
        mcp_tools=tools,
    )

    # Now read all chunks; the NEW chunks (post-seed) must include at least
    # one with 'Rhett Shull' in cross_source_match_candidates.
    all_chunks = [
        json.loads(ln) for ln in chunks_path.read_text("utf-8").splitlines() if ln
    ]
    new_chunks = [c for c in all_chunks if c.get("id") != "manual-1"]
    assert new_chunks, "No new chunks were written by the escalation."
    matched = [
        c for c in new_chunks
        if "Rhett Shull" in (c.get("cross_source_match_candidates") or [])
    ]
    assert matched, (
        "Expected at least one new chunk to corroborate the prior chunk via "
        "'Rhett Shull' in cross_source_match_candidates; got: "
        f"{[c.get('cross_source_match_candidates') for c in new_chunks]!r}"
    )
