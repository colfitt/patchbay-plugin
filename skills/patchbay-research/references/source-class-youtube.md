# Source class: YouTube

The multimodal-secondary source class for `/patchbay:research`. Validated in spike-findings § 002c. YouTube is the **secondary** research substrate — manuals and web articles outrank it — but it is the only source class that captures information visible on-screen during a gear walkthrough.

## URL patterns matched

| URL shape | Example | Routed? |
|---|---|---|
| `https://www.youtube.com/watch?v=<id>` | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` | yes |
| `https://youtube.com/watch?v=<id>` | `https://youtube.com/watch?v=dQw4w9WgXcQ` | yes |
| `https://m.youtube.com/watch?v=<id>` | `https://m.youtube.com/watch?v=dQw4w9WgXcQ` | yes |
| `https://youtu.be/<id>` | `https://youtu.be/dQw4w9WgXcQ` | yes |
| `https://www.youtube.com/@channel` (no `/watch`) | `https://www.youtube.com/@RhettShull` | no |
| Non-http(s) schemes (`javascript:`, `file://`, …) | `javascript:alert(1)` | no — rejected before host check |

`match_url` validates scheme membership against `{"http", "https"}` and host membership against an exact set — never substring containment. The first-segment id of a `youtu.be` URL is accepted as-is (validation lives downstream in `_video_id_from_url`).

## Pipeline (locked, from spike 002c)

YouTube does NOT do a tier-1 static HTML GET. `/watch` pages are JS-heavy and useless as static HTML. Instead `fetch_tier1` returns a sentinel `{status: 0, body: "", needs_pipeline: True, url_attempted: <url>}` and the SKILL driver dispatches directly to `parse_to_chunks`, which orchestrates:

```
parse_to_chunks(fetch_result, gear_ctx)
        ↓
make_tempdir()                       # tempfile.mkdtemp(prefix="patchbay-yt-") — NEVER under gear_root
        ↓
yt_pipeline.fetch_video_assets()     # yt-dlp pulls .vtt captions + 720p .mp4
        ↓
yt_pipeline._parse_vtt_safe()        # parse_vtt.py → 30s caption windows
        ↓
yt_pipeline.sample_frames()          # ffmpeg fps=1/30 → frame_NNN.jpg
        ↓
yt_pipeline.build_multimodal_chunks()
   • one `transcript` chunk per caption window (always)
   • one `multimodal_segment` chunk per (window, frame) pair
       — content.frame_description = "<<PENDING_READ_TOOL_DESCRIPTION>>"
       — provenance.frame_path     = absolute path to the frame .jpg
        ↓
SKILL.md two-pass enrichment loop (separate execution step):
   for each multimodal_segment chunk whose frame_description == sentinel:
       Read provenance.frame_path  →  one-sentence visual description
       write_chunk.update_chunk_field(chunks_jsonl, chunk_id,
           "content.frame_description", <description>)
        ↓
shutil.rmtree(tempdir)               # caller's try/finally — tempdir is gone
```

The two-pass model is load-bearing. Frame `.jpg` files live in the per-run tempdir; when the run completes, the tempdir is wiped. The SKILL driver MUST complete the enrichment loop before the research run returns control. If the frame path no longer exists on disk by the time the driver reads it, the placeholder is overwritten with the literal string `"frame unavailable"` (documented in SKILL.md) rather than left in place.

## Chunk-type mapping

| Chunk type | Emit rule | Notes |
|---|---|---|
| `transcript` | one per caption window | `content: {start_time, end_time, text}`. Always emitted. |
| `multimodal_segment` | one per `(window, frame)` pair | `content: {timestamp, frame, frame_description, caption_text, what_audio_misses}`. `frame_description` starts as the sentinel placeholder; the SKILL driver overwrites it. |
| `external_resource` | reserved for future | yt-dlp also produces the video description JSON; a future enhancement walks it for gear-relevant URLs and emits `external_resource` chunks. v1 does not. |

Every chunk: `source: "youtube"`, `tier_used: 1`, `provenance.url`, `provenance.deep_link` (with `&t=<seconds>s` or `?t=<seconds>s`), `provenance.timestamp_display`, `provenance.scraped_at`. Multimodal chunks additionally carry `provenance.frame_path`.

## NO Whisper dependency (RESEARCH-07)

Auto-captions are the only audio-text layer in v1. Spike 002a validated their sufficiency for the audio side of the multimodal pair. Whisper is a separate spike candidate, not a v1 dependency. Anyone reviewing this module for compliance with RESEARCH-07 should grep the codebase: **no `whisper`, `faster-whisper`, or `openai-whisper` imports anywhere.**

## Two-pass model: pipeline placeholder + SKILL-driven enrichment

The pipeline emits multimodal chunks with `<<PENDING_READ_TOOL_DESCRIPTION>>` as the placeholder for `content.frame_description`. The SKILL driver's second pass:

1. After `write_chunks(...)` writes the multimodal chunks to `chunks.jsonl`, iterate over them.
2. For each chunk whose `content.frame_description == "<<PENDING_READ_TOOL_DESCRIPTION>>"`:
   - Read the local image at `provenance.frame_path` via the Read tool.
   - Generate a one-sentence description of what is visually distinguishable on screen (gear visible, hands on controls, on-screen text/labels, anything the caption alone misses).
   - Call `write_chunk.update_chunk_field(chunks_jsonl_path, chunk_id, "content.frame_description", <description>)` from the Plan 01 helper to overwrite the placeholder atomically (atomic via `tempfile.mkstemp` + `os.replace`).
3. Continue until no chunk in the current run still contains the sentinel.

`update_chunk_field` was provisioned in Plan 01 specifically for this hook. If `provenance.frame_path` no longer exists on disk (tempdir was cleaned up), the driver overwrites the placeholder with `"frame unavailable"` rather than leaving the sentinel in place.

## System dependencies

| Dependency | Purpose | Install |
|---|---|---|
| `yt-dlp` | Caption + 720p video download | `brew install yt-dlp` or `pipx install yt-dlp` |
| `ffmpeg` | Frame sampling at 1/30 fps | `brew install ffmpeg` |

Both must be on `PATH`. If `yt-dlp` is missing, `parse_to_chunks` records a failure record (`reason: other`, `reason_detail: yt-dlp not installed`, `suggested_escalation: skip`) and returns `[]`. If `ffmpeg` is missing, the pipeline degrades to transcript-only chunks (no multimodal pairs).

## Security mitigations

| Threat ID | Description | Mitigation |
|---|---|---|
| T-03-20 | RCE via shell metacharacters in URL | Every `subprocess.run` uses `shell=False` with an argv list. URL is one argv element — never interpolated into a string. |
| T-03-21 | argv smuggling via crafted `v=` query value | After URL parsing, the video_id is validated against `^[A-Za-z0-9_-]{6,20}$`. Reject otherwise (returns `"unknown"`). |
| T-03-22 | Writing tempfiles inside user's gear_root | Tempdir created via `tempfile.mkdtemp(prefix="patchbay-yt-")` — system temp, NEVER under gear_root. Cleaned up via `shutil.rmtree` in try/finally. |
| T-03-24 | URL scheme abuse / host substring | Reject non-http(s) schemes. Exact-host set membership (`netloc.lower() in {…}`). |
| T-03-25 | DoS — 10-hour videos pull multi-GB | Accepted risk: 720p cap + 10-min subprocess timeout. User accepts download cost when invoking the source class. |

## UI layer notes

Per project memory (parallel UI notes required), this section documents how the future hover-citation UX consumes YouTube chunks. The data shapes are designed so the CLI flow and the eventual UI never diverge.

| Affordance | Implementation |
|---|---|
| Per-window deep-link | `provenance.deep_link` carries `&t=<seconds>s` (or `?t=<seconds>s` for `youtu.be` URLs). The UI renders this as a clickable timestamp pill that jumps the embedded player to the cited moment. The CLI surfaces the same string as a raw URL — same data, different render. |
| Frame thumbnail rendering (YouTube-specific) | For every `multimodal_segment` chunk, the UI displays the actual frame jpeg next to the caption text so the user sees what was on-screen when the caption was spoken (this is the spike-002 effect-list-on-screen moment). The thumbnail loads from `provenance.frame_path` during the same session, or from a CDN-cached copy after a "promote frames" pass that copies them under `<gear_root>/<Brand Item>/knowledge/frames/`. |
| Synthesized frame description as alt-text | `content.frame_description` (filled by the SKILL driver's two-pass enrichment) renders as the thumbnail's `alt` attribute — accessibility-first, and surfacing the visual-text delta to screen readers. |
| `transcript`-only fallback (no frame) | A `transcript` chunk emits even when the matching frame index is out of range (caption windows beyond frame count). The UI renders it as a caption-only row with the same deep-link affordance but no thumbnail. |
| Two-pass enrichment status badge | Chunks whose `content.frame_description` still equals `<<PENDING_READ_TOOL_DESCRIPTION>>` render with a "pending vision review" badge so the user can re-trigger the enrichment loop (failure mode: the tempdir was cleaned before the driver finished). |
| `what_audio_misses` callout | When the SKILL driver populates `what_audio_misses` (a delta describing visual-only signal not in the caption), the UI surfaces it as a "what the audio misses" sidebar — the explicit comparison that justifies the multimodal cost. |

## Worked-example chunk shapes

### `transcript`

```json
{
  "id": "yt-dQw4w9WgXcQ-transcript-001",
  "type": "transcript",
  "source": "youtube",
  "content": {
    "start_time": 0.0,
    "end_time": 30.0,
    "text": "hey what's up everyone welcome to the review of the boss bf three"
  },
  "tier_used": 1,
  "provenance": {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "deep_link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=0s",
    "timestamp_display": "0:00–0:30",
    "scraped_at": "2026-05-16T02:30:00Z"
  }
}
```

### `multimodal_segment` (pre-enrichment)

```json
{
  "id": "yt-dQw4w9WgXcQ-mm-002",
  "type": "multimodal_segment",
  "source": "youtube",
  "content": {
    "timestamp": 405.0,
    "frame": "frame_014.jpg",
    "frame_description": "<<PENDING_READ_TOOL_DESCRIPTION>>",
    "caption_text": "this thing has twenty eight different effects types let me show you",
    "what_audio_misses": ""
  },
  "tier_used": 1,
  "provenance": {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "deep_link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=405s",
    "timestamp_display": "6:45–7:15",
    "frame_path": "/tmp/patchbay-yt-XXXX/frames/frame_014.jpg",
    "scraped_at": "2026-05-16T02:30:00Z"
  }
}
```

### `multimodal_segment` (post-enrichment, after SKILL driver Reads the frame)

```json
{
  "id": "yt-dQw4w9WgXcQ-mm-002",
  "type": "multimodal_segment",
  "source": "youtube",
  "content": {
    "timestamp": 405.0,
    "frame": "frame_014.jpg",
    "frame_description": "KNOB FX menu on display: 'Reverb Lrg' top-left, 'All Pads' middle-top, 'Bypass' on right. Effect list visible: HP Filter, LP Filter, BP Filter, Bus Compressor (highlighted/selected), Limiter, Pumper.",
    "caption_text": "this thing has twenty eight different effects types let me show you",
    "what_audio_misses": "MAJOR visual signal: the actual list of available KNOB FX is on screen — HP Filter, LP Filter, BP Filter, Bus Compressor, Limiter, Pumper."
  },
  "tier_used": 1,
  "provenance": { /* unchanged */ }
}
```

## Citations

- Spike `sources/002a-yt-captions-only/` — VTT parser (production-ready)
- Spike `sources/002c-yt-multimodal-sampled/` — frame sampling + vision (production-ready secondary)
- Reference `youtube-ingestion.md` in `spike-findings-patchbay-plugin` — pipeline shape + chunk schema source of truth

## What this source class does NOT do

- Does **not** run Whisper. Auto-captions only.
- Does **not** auto-trigger the second pass — the SKILL driver does that explicitly per the loop in SKILL.md § YouTube two-pass enrichment.
- Does **not** sample frames denser than 1/30. Spike 002c showed ~10 of 27 sampled frames were visually distinct; scene-change filtering is a future enhancement, not v1.
- Does **not** persist frame `.jpg` files past the research run. Frames live in a per-run tempdir that is removed in `parse_to_chunks`'s try/finally. A future "promote frames" pass can copy them under `<gear_root>/<Brand Item>/knowledge/frames/` if the user wants UI-side thumbnails.
