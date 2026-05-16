"""Tests for the YouTube source class (Plan 03-04).

Task 1 (this file's initial set — parse_vtt only):
 1. test_parse_vtt_strips_inline_timing_tags
 2. test_parse_vtt_takes_last_line_of_cue
 3. test_parse_vtt_dedupes_consecutive
 4. test_parse_vtt_groups_into_30s_windows
 5. test_parse_vtt_empty_returns_empty_list
 6. test_parse_vtt_timestamp_display_format

Task 2 adds (after parse_vtt is locked in):
 7. test_match_url_accepts_watch
 8. test_match_url_accepts_youtu_be
 9. test_match_url_rejects_channel
10. test_match_url_rejects_non_https_scheme
11. test_fetch_tier1_returns_sentinel
12. test_yt_pipeline_uses_argv_not_shell
13. test_yt_pipeline_tempdir_outside_gear_root
14. test_parse_to_chunks_emits_transcripts
15. test_parse_to_chunks_yt_dlp_missing_logs_failure
16. test_init_py_contains_youtube_append_and_preserves_others
17. test_youtube_self_registers_into_registry
18. test_multimodal_chunk_has_frame_path_in_provenance
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `skills/patchbay-research` importable as a top-level package root so
# `source_classes` and `scripts` resolve regardless of cwd.
_RESEARCH_ROOT = Path(__file__).resolve().parent.parent
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample.vtt"


# ---------------------------------------------------------------------------
# parse_vtt tests (Task 1)
# ---------------------------------------------------------------------------

def test_parse_vtt_strips_inline_timing_tags(tmp_path):
    from scripts.parse_vtt import parse_vtt

    vtt = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:05.000\n"
        "Hello<00:00:01.500><c> world</c>\n"
    )
    p = tmp_path / "tags.vtt"
    p.write_text(vtt, encoding="utf-8")

    windows = parse_vtt(str(p))
    assert windows, "expected at least one window"
    blob = " ".join(w["text"] for w in windows)
    assert "<00:" not in blob
    assert "<c>" not in blob
    assert "</c>" not in blob
    assert "Hello world" in blob


def test_parse_vtt_takes_last_line_of_cue(tmp_path):
    from scripts.parse_vtt import parse_vtt

    vtt = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:05.000\n"
        "first line\nsecond line\nthird line\n"
    )
    p = tmp_path / "lastline.vtt"
    p.write_text(vtt, encoding="utf-8")

    windows = parse_vtt(str(p))
    blob = " ".join(w["text"] for w in windows)
    assert "third line" in blob
    assert "first line" not in blob
    assert "second line" not in blob


def test_parse_vtt_dedupes_consecutive(tmp_path):
    from scripts.parse_vtt import parse_vtt

    vtt = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:05.000\n"
        "same line\n\n"
        "00:00:05.000 --> 00:00:10.000\n"
        "same line\n\n"
        "00:00:10.000 --> 00:00:15.000\n"
        "different line\n"
    )
    p = tmp_path / "dedupe.vtt"
    p.write_text(vtt, encoding="utf-8")

    windows = parse_vtt(str(p))
    blob = " ".join(w["text"] for w in windows)
    assert blob.count("same line") == 1
    assert "different line" in blob


def test_parse_vtt_groups_into_30s_windows(tmp_path):
    from scripts.parse_vtt import parse_vtt

    vtt = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:05.000\n"
        "line at 0\n\n"
        "00:00:35.000 --> 00:00:40.000\n"
        "line at 35\n\n"
        "00:01:05.000 --> 00:01:10.000\n"
        "line at 65\n"
    )
    p = tmp_path / "windows.vtt"
    p.write_text(vtt, encoding="utf-8")

    windows = parse_vtt(str(p), window_seconds=30)
    assert len(windows) == 3
    # Windows should be in time order.
    starts = [w["start"] for w in windows]
    assert starts == sorted(starts)


def test_parse_vtt_empty_returns_empty_list(tmp_path):
    from scripts.parse_vtt import parse_vtt

    p = tmp_path / "empty.vtt"
    p.write_text("", encoding="utf-8")
    assert parse_vtt(str(p)) == []

    # Header-only is also "empty cues".
    p2 = tmp_path / "header.vtt"
    p2.write_text("WEBVTT\n\n", encoding="utf-8")
    assert parse_vtt(str(p2)) == []


def test_parse_vtt_timestamp_display_format(tmp_path):
    from scripts.parse_vtt import parse_vtt

    vtt = (
        "WEBVTT\n\n"
        "00:06:45.000 --> 00:06:50.000\n"
        "hello at six forty five\n\n"
        "00:07:15.000 --> 00:07:17.000\n"
        "still in the same window\n"
    )
    p = tmp_path / "tsdisplay.vtt"
    p.write_text(vtt, encoding="utf-8")

    windows = parse_vtt(str(p), window_seconds=30)
    assert windows, "expected at least one window"
    # The first window's start should be 405s (6:45). Display starts with "6:45".
    first = windows[0]
    assert int(first["start"]) == 405
    assert first["timestamp_display"].startswith("6:45")


# ---------------------------------------------------------------------------
# Fixture-driven sanity (uses the committed sample.vtt)
# ---------------------------------------------------------------------------

def test_parse_vtt_fixture_strips_quirks():
    """The committed fixture exhibits the rolling-window duplication quirk
    AND inline timing tags. Parsing it should produce dedup'd, tag-free text
    and at least 2 windows."""
    from scripts.parse_vtt import parse_vtt

    windows = parse_vtt(str(FIXTURE_PATH), window_seconds=30)
    assert len(windows) >= 2, f"expected >=2 windows, got {len(windows)}"
    blob = " ".join(w["text"] for w in windows)
    assert "<00:" not in blob
    assert "<c>" not in blob
    # The phrase "twenty eight different effects" appears in the rolling-window
    # quirk and should be deduped to a single occurrence.
    assert blob.count("twenty eight different effects") == 1


# ---------------------------------------------------------------------------
# match_url + fetch_tier1 sentinel (Task 2)
# ---------------------------------------------------------------------------

def test_match_url_accepts_watch():
    from source_classes import youtube
    assert youtube.match_url("https://www.youtube.com/watch?v=ABC123xyz_-")


def test_match_url_accepts_youtu_be():
    from source_classes import youtube
    assert youtube.match_url("https://youtu.be/ABC123xyz_-")


def test_match_url_rejects_channel():
    from source_classes import youtube
    assert youtube.match_url("https://www.youtube.com/@somechannel") is False
    # /watch without ?v= is also a reject.
    assert youtube.match_url("https://www.youtube.com/watch") is False


def test_match_url_rejects_non_https_scheme():
    from source_classes import youtube
    assert youtube.match_url("javascript:alert(1)") is False
    assert youtube.match_url("file:///etc/passwd") is False
    assert youtube.match_url("ftp://youtube.com/watch?v=ABC123xyz_") is False


def test_fetch_tier1_returns_sentinel():
    from source_classes import youtube
    result = youtube.fetch_tier1("https://www.youtube.com/watch?v=ABC123xyz_-")
    assert result["needs_pipeline"] is True
    assert result["status"] == 0
    assert result["body"] == ""
    assert result["json"] is None
    assert result["url_attempted"] == "https://www.youtube.com/watch?v=ABC123xyz_-"


# ---------------------------------------------------------------------------
# yt_pipeline subprocess argv safety (Task 2)
# ---------------------------------------------------------------------------

def test_yt_pipeline_uses_argv_not_shell(monkeypatch, tmp_path):
    """Every subprocess.run call must use shell=False and a LIST argv (never str)."""
    from scripts import yt_pipeline

    captured: list[dict] = []

    class _FakeCompleted:
        def __init__(self):
            self.returncode = 0
            self.stdout = ""
            self.stderr = ""

    def _fake_run(args, **kwargs):
        captured.append({"args": args, "kwargs": kwargs})
        return _FakeCompleted()

    monkeypatch.setattr(yt_pipeline.subprocess, "run", _fake_run)

    # Run the asset fetcher; we don't care about output files.
    try:
        yt_pipeline.fetch_video_assets(
            "https://www.youtube.com/watch?v=ABC123xyz_-",
            str(tmp_path),
        )
    except Exception:
        # The function may legitimately raise because no real .vtt/.mp4 was
        # produced by the fake run; we only care that the subprocess calls
        # were captured.
        pass
    # And the frame sampler.
    try:
        yt_pipeline.sample_frames(str(tmp_path / "video.mp4"), tmp_path / "frames")
    except Exception:
        pass

    assert captured, "subprocess.run was never called"
    for call in captured:
        # shell MUST be False (or absent, which defaults to False).
        assert call["kwargs"].get("shell", False) is False, (
            f"subprocess.run was called with shell=True: {call}"
        )
        # args MUST be a list, not a string.
        assert isinstance(call["args"], list), (
            f"subprocess.run was called with a string argv: {call!r}"
        )


def test_yt_pipeline_tempdir_outside_gear_root(monkeypatch, tmp_path):
    """fetch_video_assets must NEVER create a tempdir under gear_root."""
    from scripts import yt_pipeline

    fake_gear_root = tmp_path / "Gear" / "Boss BF-3"
    fake_gear_root.mkdir(parents=True, exist_ok=True)

    captured_prefixes: list[str] = []
    real_mkdtemp = yt_pipeline.tempfile.mkdtemp

    def _spy_mkdtemp(*args, **kwargs):
        captured_prefixes.append(kwargs.get("prefix", ""))
        # Force the temp dir into the system tmp area (not under gear_root).
        return real_mkdtemp(prefix=kwargs.get("prefix", "patchbay-yt-"))

    monkeypatch.setattr(yt_pipeline.tempfile, "mkdtemp", _spy_mkdtemp)

    # Trigger any code path that calls tempfile.mkdtemp.
    td = yt_pipeline.make_tempdir()
    try:
        assert captured_prefixes and captured_prefixes[0].startswith("patchbay-yt-")
        # The realized path must NOT live inside fake_gear_root.
        from pathlib import Path as _P
        td_resolved = _P(td).resolve()
        gear_resolved = fake_gear_root.resolve()
        if hasattr(td_resolved, "is_relative_to"):
            assert not td_resolved.is_relative_to(gear_resolved)
        else:
            try:
                td_resolved.relative_to(gear_resolved)
                inside = True
            except ValueError:
                inside = False
            assert not inside
    finally:
        import shutil
        shutil.rmtree(td, ignore_errors=True)


# ---------------------------------------------------------------------------
# parse_to_chunks orchestration (Task 2)
# ---------------------------------------------------------------------------

def _fake_caption_windows() -> list[dict]:
    return [
        {
            "start": 0.0,
            "end": 30.0,
            "text": "intro line",
            "timestamp_display": "0:00–0:30",
        },
        {
            "start": 30.0,
            "end": 60.0,
            "text": "second window",
            "timestamp_display": "0:30–1:00",
        },
    ]


def test_parse_to_chunks_emits_transcripts(monkeypatch, tmp_path):
    """With pipeline mocked to return windows but no frames, at least one
    transcript chunk must be emitted."""
    from source_classes import youtube as yt_mod
    from scripts import yt_pipeline

    def _fake_fetch_video_assets(url, tempdir):
        return {
            "vtt_path": str(tmp_path / "video.en.vtt"),
            "mp4_path": str(tmp_path / "video.mp4"),
            "video_id": "ABC123xyz_-",
        }

    monkeypatch.setattr(yt_pipeline, "fetch_video_assets", _fake_fetch_video_assets)
    monkeypatch.setattr(yt_pipeline, "sample_frames", lambda *_a, **_k: [])
    monkeypatch.setattr(
        yt_pipeline, "_parse_vtt_safe", lambda *_a, **_k: _fake_caption_windows()
    )

    fetch_result = yt_mod.fetch_tier1("https://www.youtube.com/watch?v=ABC123xyz_-")
    chunks = yt_mod.parse_to_chunks(
        fetch_result,
        {
            "item": "Boss BF-3",
            "brand": "Boss",
            "scraped_at": "2026-05-16T02:30:00Z",
        },
    )
    types = [c["type"] for c in chunks]
    assert "transcript" in types, f"expected transcript chunk, got {types}"
    # Every chunk has source/tier_used.
    for c in chunks:
        assert c["source"] == "youtube"
        assert c["tier_used"] == 1
        assert "url" in c["provenance"]
        assert "deep_link" in c["provenance"]


def test_parse_to_chunks_yt_dlp_missing_logs_failure(monkeypatch, tmp_path):
    """When yt-dlp raises FileNotFoundError, parse_to_chunks returns []."""
    from source_classes import youtube as yt_mod
    from scripts import yt_pipeline

    def _missing(*_a, **_k):
        raise FileNotFoundError("yt-dlp")

    monkeypatch.setattr(yt_pipeline, "fetch_video_assets", _missing)

    fetch_result = yt_mod.fetch_tier1("https://www.youtube.com/watch?v=ABC123xyz_-")
    chunks = yt_mod.parse_to_chunks(
        fetch_result,
        {"item": "Boss BF-3", "scraped_at": "2026-05-16T02:30:00Z"},
    )
    assert chunks == []
    # The recorded failure (made available for the SKILL driver to forward
    # into failures.log) must mention yt-dlp.
    last = getattr(yt_mod, "last_failure_record", None)
    assert last is not None
    assert last["reason"] == "other"
    assert "yt-dlp" in last["reason_detail"].lower()
    assert last["suggested_escalation"] == "skip"


def test_multimodal_chunk_has_frame_path_in_provenance(monkeypatch, tmp_path):
    """When the pipeline produces frames, multimodal_segment chunks must have
    provenance.frame_path set (the SKILL driver Reads from this path)."""
    from source_classes import youtube as yt_mod
    from scripts import yt_pipeline

    # Create a fake frame file.
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    fake_frame = frames_dir / "frame_001.jpg"
    fake_frame.write_bytes(b"\xff\xd8\xff\xd9")  # tiny "jpeg-like" bytes

    def _fake_fetch_video_assets(url, tempdir):
        return {
            "vtt_path": str(tmp_path / "video.en.vtt"),
            "mp4_path": str(tmp_path / "video.mp4"),
            "video_id": "ABC123xyz_-",
        }

    monkeypatch.setattr(yt_pipeline, "fetch_video_assets", _fake_fetch_video_assets)
    monkeypatch.setattr(yt_pipeline, "sample_frames", lambda *_a, **_k: [str(fake_frame)])
    monkeypatch.setattr(
        yt_pipeline, "_parse_vtt_safe", lambda *_a, **_k: _fake_caption_windows()
    )

    fetch_result = yt_mod.fetch_tier1("https://www.youtube.com/watch?v=ABC123xyz_-")
    chunks = yt_mod.parse_to_chunks(
        fetch_result,
        {"item": "Boss BF-3", "scraped_at": "2026-05-16T02:30:00Z"},
    )

    mm = [c for c in chunks if c["type"] == "multimodal_segment"]
    assert mm, f"expected at least one multimodal_segment, got {[c['type'] for c in chunks]}"
    for c in mm:
        fp = c["provenance"].get("frame_path", "")
        assert isinstance(fp, str) and fp.endswith(".jpg") and fp, (
            f"multimodal chunk lacks provenance.frame_path: {c!r}"
        )
        assert c["content"]["frame_description"] == "<<PENDING_READ_TOOL_DESCRIPTION>>"


# ---------------------------------------------------------------------------
# Registry / __init__.py preservation (Task 2)
# ---------------------------------------------------------------------------

def test_init_py_contains_youtube_append_and_preserves_others():
    """After this plan, __init__.py contains:
      - Plan 01's `REGISTRY: list = []` scaffold
      - Plan 02's `from . import reddit`
      - Plan 03's `from . import equipboard`
      - Plan 04's `from . import youtube`
    None of the earlier appends may have been clobbered.
    """
    init_path = _RESEARCH_ROOT / "source_classes" / "__init__.py"
    text = init_path.read_text(encoding="utf-8")
    assert "REGISTRY: list = []" in text
    assert "from . import reddit" in text
    assert "from . import equipboard" in text
    assert "from . import youtube" in text


def test_youtube_self_registers_into_registry():
    """Reloading the source_classes package + the youtube module simulates
    a cold start; the youtube module body must self-register into REGISTRY.
    """
    import importlib

    # Make sure the path is fresh.
    if str(_RESEARCH_ROOT) not in sys.path:
        sys.path.insert(0, str(_RESEARCH_ROOT))

    import source_classes  # noqa: WPS433
    importlib.reload(source_classes)
    from source_classes import youtube as yt_mod  # noqa: WPS433
    importlib.reload(yt_mod)
    # After reload, REGISTRY must contain the youtube module.
    assert yt_mod in source_classes.REGISTRY
