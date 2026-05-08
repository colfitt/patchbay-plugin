---
spike: 002c
name: yt-multimodal-sampled
type: comparison
validates: "Given a YouTube tutorial URL, when auto-captions are paired with sampled video frames + per-frame visual analysis at the same timestamps, then the chunks capture both spoken and demonstrated content — closing the gap that transcript-only ingest leaves open"
verdict: VALIDATED
related: [002a]
tags: [research, youtube, transcript, multimodal, frames, vision]
---

# Spike 002c: YouTube multimodal — captions + sampled frames + analysis

## What This Validates

The full architectural answer to the user's question "is just transcription the best way to get YT info?" — *no, multimodal beats transcript-only for gear tutorials.* The spike pairs auto-captions with video frames sampled at 30s intervals, runs each frame through Claude's vision (the same Read tool that powered spike 001), and merges them into chunks that capture both **what was said** and **what was shown**.

## Research

| Approach | Tool | Pros | Cons | Status |
|----------|------|------|------|--------|
| **yt-dlp + ffmpeg + Claude vision** | yt-dlp + ffmpeg + Read tool | Mirrors production (the skill IS Claude), no API costs, frames + transcript share the same chunk schema as manual ingest (spike 001) | Frame sampling is sparse — interesting moments between samples are missed unless sampling rate is high | **Chosen** |
| Whisper-transcribed audio + frames | OpenAI Whisper API + ffmpeg + Claude vision | Better transcript than auto-captions | Adds API cost and complexity; the captions-vs-Whisper question is orthogonal to the multimodal-vs-transcript question this spike asks | Deferred to follow-up spike |
| Per-second frame sampling + OCR | ffmpeg dense + tesseract | Catches every visual event | 13:29 video × 60s/min = ~800 frames; expensive vision token cost; mostly redundant frames | Rejected for spike scope |
| Scene-change detection sampling | ffmpeg `-vf select='gt(scene,0.3)'` | Samples only when content changes | Brittle for tutorial videos that hold long static shots of the device | Worth trying in production, deferred for spike |

**Chosen approach:** Same Claude vision pipeline as spike 001 — sample frames, run them through the Read tool, write descriptions inline. Production version is the same architecture; this spike *is* the production code shape.

## How to Run

```bash
cd .planning/spikes/002c-yt-multimodal-sampled

# Pull video at 720p
yt-dlp -f "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]" \
       --merge-output-format mp4 \
       --output 'raw/%(id)s.%(ext)s' \
       "https://www.youtube.com/watch?v=Q3DzJ2t6p68"

# Sample frames every 30 seconds
ffmpeg -i raw/Q3DzJ2t6p68.mp4 -vf "fps=1/30" -q:v 3 frames/frame_%03d.jpg
```

Then for each sampled frame, Claude (the human in the loop, or the agent at production time) reads the image via the Read tool and writes a description into `chunks/chunks.json` with the same schema 002a uses for captions, plus `frame`, `frame_description`, and a `what_audio_misses` field.

Open the comparison viewer at `http://localhost:8766/002-yt-comparison-viewer.html`.

## What to Expect

10 chunks, sampled strategically across the video to cover every distinct mode/scene the tutorial demonstrates:

| ts | What's visible |
|----|----------------|
| 0:00 | Establishing shot — host with Quickstart Guide |
| 0:30 | Clean top-down panel — every control labeled |
| 1:00 | Host demonstrating PADs / fader |
| 1:30 | "START RECORDING" overlay + count-in '2' on display |
| 2:00 | SEQ MODE active — tempo, bar, Q-rate visible on screen |
| 3:00 | SAMPLE RECORD mode — "Tap pad to record" interface |
| 5:00 | TUNE menu — Semi/Fine/Warp parameters revealed |
| 7:00 | KNOB FX menu — full effect list visible (HP/LP/BP Filter, Bus Compressor, Limiter, Pumper) |
| 9:30 | Pad bank B + both PAD FX and KNOB FX active simultaneously |
| 12:30 | Outro / closing teaser — user-trimmed sample shown |

Each chunk includes a `what_audio_misses` field — the explicit comparison to 002a, calling out specifically what visual information would be lost if you only had the captions.

## Investigation Trail

**Iteration 1 — sampling rate.** Started at 30s/frame. With a 13:29 video that's 27 frames. Validated this gave good coverage of the distinct UI modes the tutorial demonstrates. Denser sampling would catch transitions but most are redundant for a slow-paced walkthrough.

**Iteration 2 — frame selection bias.** Of the 27 sampled frames, ~10 had distinctly different visual content (different display state, different mode, different overlay). The other 17 were variations on the same product shot. For the spike, described only the 10 distinct frames — production should add scene-change filtering to skip the redundant ones.

**Iteration 3 — chunk schema fit.** The 002c chunk schema (`timestamp`, `frame`, `frame_description`, `caption_text`, `what_audio_misses`) is a superset of 002a's (`start_time`/`end_time`/`text`). The two formats can be unified at production time — multimodal chunks are just transcript chunks with optional `frame_*` fields populated.

**Iteration 4 — alignment quirk discovered.** At t=570s, the frame shows pad bank B with both FX modes active (a state from the *previous* segment), while the audio narration has moved on to talking about SD card save/load. This is a real alignment quirk — visual state can lag audio context — and the production system needs to handle it gracefully (maybe sample N frames around each audio segment and pick the most relevant?).

## Results

**Verdict: VALIDATED — but secondary.** User read the comparison viewer side-by-side and concluded: "the multimodal is very close, a great reference tool to the manual. Terms can probably be linked easily. The manual and reviews and just web searching might be better, just because it's text and pictures from scraping. But this is still a good tool to have, not the best tool, but good enough."

### Verified findings

- **Multimodal closes the gap that captions-only leaves open.** The KNOB FX moment (t=7:00) was decisive: captions say "28 different effects types"; the frame shows the actual list (HP/LP/BP Filter, Bus Compressor, Limiter, Pumper). That's a quantum leap in usable knowledge.
- **Terminology aligns with manual chunks.** The MPC's UI labels visible in the frames (KNOB FX, PAD FX, Trim, Tune, Filter, Semi Tune / Fine Tune / Warp) match the labels described in spike 001's manual chunks. Cross-source citation will work — a user asking "what does Knob FX do?" can be answered from manual page 51 (chunk) AND linked to the YT moment at t=7:00 demonstrating it.
- **The chunk schema unifies.** Manual chunks and YT multimodal chunks share the same shape (`source`, `content/description`, `provenance`). Architecture confirmed.
- **Build cost is real but bounded.** yt-dlp + ffmpeg + Claude vision is the same pipeline as spike 001's manual ingest. Production cost is mostly the per-frame vision tokens.

### Surprises and qualifications

- **User identified a higher-leverage source class.** Web articles, gear reviews, and search-result text+images come pre-aligned (no audio-visual gap) and are easier to scrape with provenance intact. The user explicitly ranked these *above* YouTube multimodal as the next ingestion target. This pivots the immediate roadmap.
- **The alignment quirk at t=9:30** (frame shows previous demo's state while audio has moved on) was noted as a production-detail to handle, not a blocker. Sampling N frames per audio segment and picking the most relevant is a post-spike production refinement.
- **YT multimodal is a "good tool, not the best tool."** Production version of `patchbay:research` should treat YouTube as a secondary source — surface it for technique demos and tutorials where seeing the host's hands matters, but not as the primary research substrate.

### Impact on the next spike

The next high-leverage unknown is no longer Whisper-vs-captions or scene-change detection. It's:

> **Spike 003: scrape web articles and reviews into the same chunk schema.**

If text+images from the web produces chunks at parity with the manual ingest (cleanly aligned, citable, provenance-anchored), it becomes the primary `patchbay:research` path and YouTube becomes optional polish.
