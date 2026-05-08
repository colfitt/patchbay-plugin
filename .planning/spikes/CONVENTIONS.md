# Spike Conventions

Patterns and stack choices established across spike sessions for the patchbay-plugin project. New spikes follow these unless the question specifically requires otherwise.

## Stack

**Language:** Python 3 for parsers and helper scripts (used in all four spikes — VTT parser, JSON inlining, frame metadata extraction). No package.json, no JS build step. The skill IS Claude Code, so production pipelines exploit Claude's native tools (Read tool for PDF/image vision) rather than introducing separate runtimes.

**Vision pipeline:** Claude's Read tool with PDF support (up to 20 pages/call) — used in spikes 001 and 002c. No SDK, no API key, no per-page rendering pipeline at production time. Mirrors the production code shape directly.

**Helper tools:** `pdftoppm` (manual page rendering for viewers, NOT for production ingest), `ffmpeg` (video frame sampling — required dep for YT spikes), `yt-dlp` (YouTube fetch — captions, audio, video, metadata). Install via `brew install ffmpeg yt-dlp poppler`.

**Web fetch:** `curl` for tier-1 static fetch tests in spikes. Production should use `requests` + `BeautifulSoup` for the same role. `Claude_in_Chrome` MCP for tier-2 escalation — drives the user's actual Chrome.

## Structure

```
.planning/spikes/NNN-spike-name/
├── README.md             # YAML frontmatter (spike, name, type, validates, verdict, related, tags) + sections
├── viewer.html           # side-by-side comparison viewer for human verification
├── chunks/               # structured output of the spike
│   └── chunks.json       # OR eb-chunks.json + reddit-chunks.json for multi-source spikes
├── raw/                  # original input (PDF references via path, video files, scraped HTML, JSON dumps)
├── pages-rendered/       # PNG renders of paginated source — for viewer side-by-side only
└── frames/               # ffmpeg-extracted video frames — for viewer side-by-side only
```

Comparison spikes use shared number with letter suffix: `002a-yt-captions-only/`, `002c-yt-multimodal-sampled/`, with a single comparison viewer at `.planning/spikes/002-yt-comparison-viewer.html`.

## Patterns

### Side-by-side verification viewer (recurring across all spikes)

Single-file HTML with chunks inlined as JS const, no fetch, dark theme with semantic badge colors, two-column-always (no responsive collapse). See [`.claude/skills/spike-findings-patchbay-plugin/references/spike-pattern.md`](../../.claude/skills/spike-findings-patchbay-plugin/references/spike-pattern.md) for the full template.

### Inline-chunks pattern

```python
# Write viewer with placeholder: const CHUNKS = /*__CHUNKS__*/[];
# Then inline:
html = open(viewer_path).read()
chunks = open(chunks_path).read().strip()
open(viewer_path, 'w').write(html.replace('/*__CHUNKS__*/[]', chunks))
```

### Server config

Each spike gets its own port in `.claude/launch.json`:

```json
{ "name": "spike-NNN-viewer", "runtimeExecutable": "python3",
  "runtimeArgs": ["-m", "http.server", "8767", "--directory", ".planning/spikes/NNN-spike-name"],
  "port": 8767 }
```

Ports used so far: 8765 (spike-001), 8766 (spike-002 — root spikes dir for cross-spike viewer), 8767 (spike-003). Future spikes: 8768, 8769, ...

### Verification protocol

1. Build the viewer with chunks inlined.
2. `mcp__Claude_Preview__preview_start` with the named launch config.
3. `mcp__Claude_Preview__preview_eval` to confirm chunks loaded and rendered (count check).
4. `mcp__Claude_Preview__preview_screenshot` to capture state.
5. Present a CHECKPOINT box with specific timestamps/pages and explicit verdict questions.
6. Wait for user verdict. Update README Results section + MANIFEST verdict.
7. Commit using `docs(spike-NNN): [VERDICT] — [key finding]` format.

### Commit messages

`docs(spike-NNN): [VERDICT] — [key finding]` — verdict in `[VALIDATED]` / `[PARTIAL]` / `[INVALIDATED]` form. Multi-spike commits: `docs(spike-NNN): [VERDICT-A/VERDICT-B] — [...]`.

## Tools & Libraries

- **`yt-dlp`** — YouTube fetch (captions, audio, video, metadata). Pinned via Homebrew; recent enough versions handle all current YouTube quirks.
- **`ffmpeg`** — required for yt-dlp's audio/video merging AND for frame sampling.
- **`pdftoppm`** (poppler) — PDF page → PNG rendering. ONLY for viewers, not production ingest.
- **Python stdlib** — `json`, `re`, `pathlib`. Stay deps-free where possible.
- **No `BeautifulSoup` yet** in spikes — but it's the recommended tier-1 web parser for production.
- **No Whisper, no PRAW, no Playwright** — explicitly deferred. v1 ships without them.

## Anti-patterns (don't introduce these in new spikes)

- **No build step.** No Vite, no webpack, no TypeScript compiler. Spikes are throwaway-fast or they're not really spikes.
- **No raw video commits.** `.planning/spikes/.gitignore` excludes `*.mp4`, `*.m4a`, `*.webm`, `*.mkv`. Frames + chunks ARE committed.
- **No fetch-from-disk in viewers.** Inline chunks as JS const. file:// + fetch silently fails.
- **No auto-fallback in production code.** Tier escalation is user-driven (per spike 003 architectural decision).
