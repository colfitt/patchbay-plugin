"""VTT caption parser for YouTube auto-captions.

YouTube's auto-caption `.vtt` format is a rolling-window stream: each cue
typically contains the "previous line" (already-spoken) on the first line
and the "current line" (still being typed in word-by-word) on the second.
Inline timing tags like `<00:00:02.639><c>...</c>` mark which word the
typewriter cursor is on. A naive line-by-line parse produces 3× duplication.

This parser:
  1. Strips inline timing tags (`<\\d\\d:\\d\\d:\\d\\d\\.\\d{3}>` and `</c>` / `<c>`).
  2. Takes ONLY the last non-empty line of each cue body — the "current" caption.
  3. Dedupes consecutive identical lines across cues.
  4. Groups lines into N-second windows (default 30s) by cue start time.
  5. Returns `[]` for an empty / no-cues VTT (never raises).

Output shape per window: `{start: float, end: float, text: str, timestamp_display: str}`
where `timestamp_display` is `"M:SS–M:SS"` (en-dash, no leading-zero on minutes).

SECURITY (T-03-19):
  The path is resolved via `pathlib.Path(...).resolve()` and verified to be
  a real file before reading. Opened in text mode with `errors="replace"`
  so corrupt bytes do not crash the parser. No `subprocess`, no `eval`,
  no `exec`. Stdlib only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

# Inline timing tags YouTube emits per word: <00:00:02.639><c>word</c>.
_INLINE_TIMING_RE = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")
_C_OPEN_RE = re.compile(r"<c[^>]*>")
_C_CLOSE_RE = re.compile(r"</c>")

# Cue timing line: "HH:MM:SS.mmm --> HH:MM:SS.mmm [...]"
_TIMING_LINE_RE = re.compile(
    r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _strip_inline_tags(line: str) -> str:
    """Remove inline timing tags and `<c>`/`</c>` wrappers from a caption line."""
    line = _INLINE_TIMING_RE.sub("", line)
    line = _C_OPEN_RE.sub("", line)
    line = _C_CLOSE_RE.sub("", line)
    return line.strip()


def _format_timestamp_display(start: float, end: float) -> str:
    """`M:SS–M:SS` (en-dash) with no leading-zero on minutes."""
    def fmt(t: float) -> str:
        total = int(t)
        m = total // 60
        s = total % 60
        return f"{m}:{s:02d}"
    return f"{fmt(start)}–{fmt(end)}"


def _iter_cues(text: str) -> List[Tuple[float, float, str]]:
    """Yield (start_seconds, end_seconds, last_nonempty_line_stripped) for each cue.

    A cue is recognized by a timing line; its body is the lines following
    until a blank line. The "last non-empty line" rule handles YouTube's
    rolling-window quirk: the current caption is always the last line of
    the cue body.
    """
    cues: List[Tuple[float, float, str]] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _TIMING_LINE_RE.match(line.strip())
        if not m:
            i += 1
            continue
        start = _ts_to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
        end = _ts_to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))
        # Collect body until blank line or EOF.
        body: List[str] = []
        i += 1
        while i < n and lines[i].strip() != "":
            body.append(lines[i])
            i += 1
        # Take the LAST non-empty stripped line (after stripping inline tags).
        last_clean: Optional[str] = None
        for raw in body:
            cleaned = _strip_inline_tags(raw)
            if cleaned:
                last_clean = cleaned
        if last_clean:
            cues.append((start, end, last_clean))
        # Skip the blank-line separator.
        while i < n and lines[i].strip() == "":
            i += 1
    return cues


def parse_vtt(vtt_path: str, window_seconds: int = 30) -> List[dict]:
    """Parse a YouTube auto-captions VTT file into N-second windows.

    Returns `[]` on:
      - File missing or not a regular file.
      - Empty / header-only VTT (no cues).

    Never raises on parse problems — returns whatever windows it found.
    """
    try:
        resolved = Path(vtt_path).resolve()
    except (OSError, ValueError):
        return []
    if not resolved.is_file():
        return []

    try:
        text = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    cues = _iter_cues(text)
    if not cues:
        return []

    # Dedupe consecutive identical lines.
    deduped: List[Tuple[float, float, str]] = []
    last_line: Optional[str] = None
    for start, end, line in cues:
        if line == last_line:
            continue
        deduped.append((start, end, line))
        last_line = line

    if not deduped:
        return []

    # Group into windows: each window starts at the first un-bucketed cue's
    # start time and extends `window_seconds`. Successive cues whose start
    # falls within `[window_start, window_start + window_seconds)` go into
    # the same window; the next cue starts a new one. This keeps the window's
    # `start` field anchored to the actual content (e.g., a 6:45 cue → a 6:45
    # window) rather than to a fixed 30s grid, which matters for the
    # `timestamp_display` deep-link in `provenance.deep_link`.
    out: List[dict] = []
    cur_start: Optional[float] = None
    cur_lines: List[str] = []
    cur_end: Optional[float] = None

    def _flush() -> None:
        nonlocal cur_start, cur_lines, cur_end
        if cur_start is None or not cur_lines:
            cur_start, cur_lines, cur_end = None, [], None
            return
        end_val = cur_end if cur_end is not None else cur_start + window_seconds
        out.append(
            {
                "start": float(cur_start),
                "end": float(end_val),
                "text": " ".join(cur_lines).strip(),
                "timestamp_display": _format_timestamp_display(cur_start, end_val),
            }
        )
        cur_start, cur_lines, cur_end = None, [], None

    for start, end, line in deduped:
        if cur_start is None:
            cur_start = start
            cur_end = cur_start + window_seconds
        if start >= cur_start + window_seconds:
            _flush()
            cur_start = start
            cur_end = cur_start + window_seconds
        cur_lines.append(line)
    _flush()

    return out
