---
spike: 002a
name: yt-captions-only
type: comparison
validates: "Given a YouTube tutorial URL for a piece of gear, when only auto-captions + description metadata are pulled (cheapest baseline), then the resulting timestamp-anchored chunks are useful enough on their own that the multimodal upgrade is unnecessary"
verdict: PARTIAL
related: [002c]
tags: [research, youtube, transcript, baseline]
---

# Spike 002a: YouTube captions-only baseline

## What This Validates

The cheapest possible YouTube ingest path — `yt-dlp` for auto-captions + description + metadata, no audio download, no video download, no Whisper, no frame sampling. Produces timestamp-anchored chunks with deep links back to the source video. Validates whether this baseline is *good enough* on its own, before deciding if the multimodal upgrade (002c) is worth the extra complexity.

## Research

| Approach | Tool | Pros | Cons | Status |
|----------|------|------|------|--------|
| **yt-dlp `--write-auto-sub`** | yt-dlp | Free, instant, timestamps included, works on any public video | Auto-captions are imprecise — "[music]" markers, missing punctuation, occasional wrong words for technical terms | **Chosen** |
| Whisper transcription | OpenAI API or local whisper | Higher accuracy especially for technical terms | Costs money or requires model setup; deferred to follow-up spike if 002a captions prove insufficient | Deferred |
| YouTube Data API v3 | Google API | Official, structured | Requires API key + quota; no transcript content | Skipped |

## How to Run

```bash
cd .planning/spikes
yt-dlp --write-auto-sub --sub-lang en --sub-format vtt \
       --write-info-json --write-description --skip-download \
       --output '002a-yt-captions-only/raw/%(id)s.%(ext)s' \
       "https://www.youtube.com/watch?v=Q3DzJ2t6p68"

cd 002a-yt-captions-only
python3 parse_vtt.py raw/Q3DzJ2t6p68.en.vtt chunks/chunks.json Q3DzJ2t6p68 30
```

Open the comparison viewer at `http://localhost:8766/002-yt-comparison-viewer.html` — left column shows what this spike produces.

## What to Expect

26 chunks of ~30 seconds each, ~400 chars per chunk. Each chunk has:
- `start_time` / `end_time` (seconds, float)
- `text` (deduped caption content with inline timing tags stripped)
- `provenance.deep_link` — `?t=Xs` URL that jumps to that exact moment on YouTube

Test source: "Getting Started with MPC Sample | Navigation and Sounds" — official Akai walkthrough, 13:29, 41k views.

## Investigation Trail

**Iteration 1 — VTT format quirks.** YouTube auto-captions use a rolling-window VTT format: each cue contains a "current line" plus the "next line" being typed in word-by-word. Naive parsing produces ~3× duplication. Solution: take only the *last* non-empty line of each cue body (the "current" caption being shown), then dedupe consecutive identical lines.

**Iteration 2 — inline timing tags.** Cues contain per-word `<00:00:02.639>` timing markers. Stripped via regex.

**Iteration 3 — window size.** Tested 30s windows — produced 26 chunks for a 13:29 video. Reads naturally as paragraphs. Smaller windows (10s) fragment mid-sentence; larger (60s) lose temporal precision for citation-hover.

**Iteration 4 — `[music]` markers.** Decided to keep them in the chunks. They're useful provenance signal — they tell you when the audio is filling space rather than informational.

## Results

**Verdict: PARTIAL.** Captions-only works as a cheap, fast baseline — the parser produces clean 30s-windowed chunks with timestamp anchors and deep links — but on side-by-side comparison with 002c, captions consistently left the user wanting visual context. The decisive moment was t=7:00, where captions say "28 different effects types" while the screen shows the actual list. That's information loss the user cared about.

### Verified findings

- **The pipeline works.** yt-dlp pulls auto-captions reliably; the parser handles YouTube's rolling-window VTT format; chunks get clean timestamp anchors and deep-link URLs.
- **Captions ARE good enough for some moments.** At t=0:30 (clean panel + "press the green play button") the captions are largely self-explanatory. Captions-only would suffice if the use case were "give me the gist of this tutorial."
- **Captions are NOT good enough for gear knowledge.** Patchbay's use case is gear-anchored Q&A — "what FX types does my MPC have?", "what does Knob FX show me?". For these, the visual content carries information captions skip.

### Use case for this spike's output

Captions-only is the right *fallback* — when video download/frame sampling is too expensive (long videos, many videos, batch ingestion). For curated tutorials about gear in inventory, 002c is the right path.

### Why PARTIAL not INVALIDATED

The chunks ARE useful. They produce the right shape, the right timestamp anchors, the right deep links. They're just too thin on their own. As a *layer* in the multimodal pipeline (002c uses these caption chunks alongside frame analysis), they're load-bearing. As a standalone product, they're insufficient.
