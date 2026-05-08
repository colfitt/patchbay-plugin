# YouTube Ingestion (multimodal, secondary source)

Validated in spikes 002a (PARTIAL) and 002c (VALIDATED secondary). YouTube is the **secondary** source class — useful as a reference tool for technique demos, NOT the primary research substrate. Web articles + Equipboard outrank it.

## Requirements

- All chunks honor the [chunk schema](./chunk-schema.md).
- **Multimodal, not transcript-only.** Captions alone consistently lose information visible on screen (effect lists, parameter values, mode states). The decisive moment in spike 002 was t=7:00 of the test video where captions said "28 different effects types" while the screen showed the actual list (HP/LP/BP Filter, Bus Compressor, Limiter, Pumper).
- Auto-captions are sufficient as the audio-text layer; **Whisper is not a v1 dependency.**
- Frame sampling at **30s intervals** is the right default. Denser sampling catches transitions but mostly produces redundant frames for slow-paced gear walkthroughs.
- YouTube is **secondary**, not primary. Source priority: manual → web articles/reviews → YT multimodal → YT captions-only.

## How to Build It

### Pipeline

```
Gear/<Brand Item>/youtube-tutorials/<video-url>
        ↓
   yt-dlp pulls auto-captions (.vtt) + description + info JSON
        ↓
   Parse VTT → 30s caption windows with deep-link timestamps  ← spike 002a
        ↓
   yt-dlp downloads 720p video → ffmpeg samples frames at fps=1/30
        ↓
   Claude reads each frame via Read tool → describe + categorize  ← spike 002c
        ↓
   Merge caption windows + frame descriptions at aligned timestamps
        ↓
   Write multimodal chunks to chunks.jsonl
```

### Caption parsing (spike 002a — production-ready)

`parse_vtt.py` from spike 002a is production-ready. The script handles YouTube's rolling-window VTT format (each cue contains the current line + next-line being typed in word-by-word, producing 3× duplication if naively parsed).

Key implementation notes from the spike:
1. Strip inline timing tags `<00:00:02.639><c>...</c>` via regex.
2. Take only the **last** non-empty line of each cue body (the "current" caption).
3. Dedupe consecutive identical lines.
4. Group into 30-second windows.
5. Each chunk gets `provenance.deep_link = video_url + "&t=Xs"` for citation-hover.

Source script preserved at `sources/002a-yt-captions-only/parse_vtt.py`.

### Frame sampling + vision (spike 002c — production-ready)

```bash
# Download video at 720p (caps download size, sufficient for vision)
yt-dlp -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" \
       --merge-output-format mp4 \
       --output 'video.mp4' \
       "https://www.youtube.com/watch?v=..."

# Sample frames every 30 seconds
ffmpeg -i video.mp4 -vf "fps=1/30" -q:v 3 frames/frame_%03d.jpg
```

Then for each sampled frame, the skill prompts Claude to read the image and produce a chunk in this shape:

```json
{
  "id": "yt-mm-007",
  "timestamp": 420,
  "frame": "frame_015.jpg",
  "frame_description": "KNOB FX menu on display: 'Reverb Lrg' top-left, 'All Pads' middle-top, 'Bypass' on right. Effect list visible: HP Filter, LP Filter, BP Filter, Bus Compressor (highlighted/selected), Limiter, Pumper. Bottom K1/K2/K3 labels: 'Pre-delay', 'Time', 'Mix'. KNOB FX button illuminated bright orange.",
  "caption_window": "6:45–7:17",
  "caption_text": "[caption text from same window]",
  "what_audio_misses": "MAJOR visual signal: the actual list of available KNOB FX is on screen — HP Filter, LP Filter, BP Filter, Bus Compressor, Limiter, Pumper. Audio says '28 different effects types' but doesn't name them.",
  "provenance": { ... deep_link: "youtube.com/watch?v=...&t=420s" ... }
}
```

The `what_audio_misses` field is **critical** — it's the explicit comparison that justifies the multimodal cost. If a frame doesn't add visual info beyond what captions capture, that field is short or empty (and the frame might be skippable in production).

### Frame-selection heuristic (production refinement worth implementing)

Spike 002c sampled 27 frames at 30s; only ~10 were visually distinct from each other (different display state / mode / overlay). Production should add **scene-change filtering**:

```bash
# Skip redundant frames — only sample when the scene changes meaningfully
ffmpeg -i video.mp4 -vf "select='gt(scene,0.3)',showinfo" -vsync vfr frames/scene_%03d.jpg
```

Then for each scene-change frame, snap to the nearest 30s caption boundary.

## What to Avoid

- **Don't ship transcript-only ingest as a standalone product.** Spike 002a is PARTIAL — it works as a fallback layer when video download is too expensive (long videos, batch ingestion of many videos), but on its own it loses too much info.
- **Don't over-sample frames.** 1 frame per second (60×30 = 1800 frames for a 30min video) is cost-prohibitive at vision-token rates and mostly produces redundant frames.
- **Don't ignore the alignment quirk.** Visual state can lag audio context — at t=9:30 of spike 002c's test video, the frame showed the previous demo's setup while audio had moved on to a new topic. Production should sample N frames per audio segment and pick the most relevant, OR flag the mismatch in chunk metadata.
- **Don't assume Whisper is required.** YouTube's auto-captions are good enough for the audio-text layer for v1. Whisper is a quality upgrade and a separate spike candidate, not a v1 dependency.

## Constraints

- **20-page Read tool limit doesn't apply to images** — but vision-token cost is real. Sparse sampling (every 30s, scene-change-filtered in production) is the budget-conscious default.
- **yt-dlp dependency on ffmpeg.** Don't ship without `brew install ffmpeg` documented in setup.
- **Channel-quality variance.** Pedal demo channels vary wildly; some are screen recordings (high signal per frame), some are talking-head videos (low signal). Frame sampling rate may need to be channel-aware in production.

## Origin

Synthesized from spikes 002a (PARTIAL) and 002c (VALIDATED secondary).
Source files: `sources/002a-yt-captions-only/README.md`, `sources/002a-yt-captions-only/parse_vtt.py`, `sources/002c-yt-multimodal-sampled/README.md`
