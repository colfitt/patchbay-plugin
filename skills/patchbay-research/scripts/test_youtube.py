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
