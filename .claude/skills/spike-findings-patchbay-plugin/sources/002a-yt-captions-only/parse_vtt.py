"""
Parse YouTube auto-caption VTT into chunks with timestamp anchors.

YouTube auto-captions use a rolling-window format: each cue contains the current
line PLUS the next line being typed in word-by-word. This produces massive
duplication. The strategy here:
  1. Strip inline timing tags (<00:00:02.639><c>...</c>)
  2. Drop "rolling preview" cues — the ones where the second line ends mid-word
     (those are duplicated by the next full cue)
  3. Concatenate remaining cues' final-line text into a single continuous transcript
     keyed to the cue's start timestamp
  4. Group into ~30-second windows for chunking
"""
import json, re, sys
from pathlib import Path

VTT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
VIDEO_ID = sys.argv[3]
WINDOW_SEC = int(sys.argv[4]) if len(sys.argv) > 4 else 30

ts_re = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3}) --> (\d{2}):(\d{2}):(\d{2})\.(\d{3})")
inline_tag_re = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")
ctag_re = re.compile(r"</?c[^>]*>")

def parse_ts(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

cues = []
text = VTT.read_text().splitlines()
i = 0
while i < len(text):
    m = ts_re.match(text[i] or "")
    if not m:
        i += 1
        continue
    start = parse_ts(*m.group(1, 2, 3, 4))
    end = parse_ts(*m.group(5, 6, 7, 8))
    i += 1
    body = []
    while i < len(text) and text[i].strip():
        body.append(text[i])
        i += 1
    raw = "\n".join(body)
    cleaned = ctag_re.sub("", inline_tag_re.sub("", raw)).strip()
    if cleaned:
        cues.append((start, end, cleaned))
    i += 1

# Each cue body has 1-2 lines. Take ONLY the last non-empty line — that's the
# "current" caption being shown. The first line is a copy of the previous cue's.
# Then dedupe consecutive identical lines.
final_segments = []
prev_text = None
for start, end, body in cues:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        continue
    line = lines[-1]
    if line == prev_text:
        continue
    final_segments.append((start, end, line))
    prev_text = line

# Group into windows
windows = []
window_start = None
window_end = None
window_text = []
for start, end, line in final_segments:
    if window_start is None:
        window_start = start
    if start - window_start >= WINDOW_SEC and window_text:
        windows.append((window_start, window_end, " ".join(window_text)))
        window_start = start
        window_text = []
    window_end = end
    window_text.append(line)
if window_text:
    windows.append((window_start, window_end, " ".join(window_text)))

video_url = f"https://www.youtube.com/watch?v={VIDEO_ID}"

chunks = []
for idx, (s, e, txt) in enumerate(windows):
    chunks.append({
        "id": f"yt-cap-{idx:03d}",
        "type": "transcript",
        "source": "auto-captions",
        "start_time": round(s, 2),
        "end_time": round(e, 2),
        "duration": round(e - s, 2),
        "text": txt,
        "provenance": {
            "video_id": VIDEO_ID,
            "video_url": video_url,
            "deep_link": f"{video_url}&t={int(s)}s",
            "timestamp_display": f"{int(s)//60}:{int(s)%60:02d}–{int(e)//60}:{int(e)%60:02d}"
        }
    })

OUT.write_text(json.dumps(chunks, indent=2))
print(f"wrote {len(chunks)} chunks ({sum(len(c['text']) for c in chunks)} chars total) to {OUT}")
