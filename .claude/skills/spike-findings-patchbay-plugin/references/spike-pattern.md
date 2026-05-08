# Spike Pattern (recurring template — for FUTURE spikes, not for production code)

A recurring shape emerged across all four spikes (001/002a/002c/003) for letting the user verify quality side-by-side. This isn't production architecture — it's the **template for running new spikes** so they reach a verdict quickly with strong human judgment.

## When to use

When a future spike validates **vision quality**, **transcription accuracy**, **scrape extraction quality**, or any other "is this good enough?" question that requires human judgment per-instance, build this. Don't build this for pure-fact spikes ("does this API return 200?").

## Recipe

### Directory layout

```
.planning/spikes/NNN-spike-name/
├── README.md             # frontmatter + What This Validates / Research / How to Run / Investigation Trail / Results
├── viewer.html           # the side-by-side comparison viewer
├── chunks/               # the structured output the spike produces
│   └── chunks.json
├── raw/                  # original input (PDF, video, scraped HTML, JSON dump)
└── pages-rendered/       # only when comparing against a paginated source (PDF) — rendered for the viewer
```

### Viewer template (proven across 3 spikes)

A single-file HTML viewer with chunks inlined as JS const, source content on the left, generated chunks on the right. **No fetch, no build step, no server-side anything beyond `python3 -m http.server`.**

Key UI decisions, all validated:

1. **Two-column grid, no responsive collapse.** The 1100px-breakpoint media query that stacks columns on narrow screens caused a real bug in spike 001 where the user couldn't see both sides simultaneously. Keep the two columns at any viewport width — let them shrink instead.
2. **Inline chunks as `const CHUNKS = [...]`** in the script tag. No fetch needed; viewer works on file:// protocol if needed (though serve via `http.server` to avoid CORS surprises).
3. **Sticky page/timestamp navigation at the top.** Click to jump.
4. **Dark theme with semantic badge colors.** Tier-0 (user-paste) red, tier-1 (success) green, image type categories color-coded. Provenance footer in muted monospace.
5. **`what_audio_misses` / cross-source-match insight blocks** in green — these were the highest-signal UI elements during spike verification.
6. **Filter bar at top.** "Cross-source matches only" filter was the killer feature for spike 003.

### Inline-chunks helper

After writing the viewer with placeholder `const CHUNKS = /*__CHUNKS__*/[];`, run this to inline:

```python
import json
viewer_path = '...viewer.html'
chunks_path = '...chunks.json'
with open(viewer_path) as f: html = f.read()
with open(chunks_path) as f: chunks = f.read().strip()
out = html.replace('/*__CHUNKS__*/[]', chunks)
with open(viewer_path, 'w') as f: f.write(out)
```

For multi-source viewers (spike 002, 003), use multiple placeholders: `/*__EB__*/[]`, `/*__RD__*/[]`, etc.

### Server config (.claude/launch.json)

Each spike gets its own port to avoid conflicts:

```json
{
  "version": "0.0.1",
  "configurations": [
    { "name": "spike-NNN-viewer", "runtimeExecutable": "python3",
      "runtimeArgs": ["-m", "http.server", "8767", "--directory", ".planning/spikes/NNN-spike-name"],
      "port": 8767 }
  ]
}
```

Then `mcp__Claude_Preview__preview_start` with the named config. Verify via `preview_eval` and `preview_screenshot`.

### Verification flow

1. Build the viewer
2. Start the preview server  
3. `preview_eval` to confirm chunks loaded and rendered
4. `preview_screenshot` to capture the current state
5. Present the user with explicit checkpoint questions tied to specific timestamps/pages
6. Wait for verdict; update README Results section; update MANIFEST verdict

## Anti-patterns (don't do these)

- **Don't ship the viewer with a `fetch('/chunks.json')` call.** It silently fails on file:// and on some preview environments. Inline the data.
- **Don't gate the viewer on a build step (Vite, webpack, etc.).** Spikes are throwaway; setup overhead kills the iteration speed.
- **Don't auto-collapse layout on narrow screens.** See above — caused a real bug in spike 001.
- **Don't commit raw video files** (`.mp4` 30-50MB+ per video). Spike 002 added `.planning/spikes/.gitignore` for this. Frames + chunks ARE committed.
- **Don't write multi-paragraph "summary" sections in the viewer.** The point is side-by-side comparison; commentary belongs in the README.

## Origin

Pattern emerged across spikes 001 (manual viewer), 002 (YT comparison viewer), 003 (web ingest viewer). Each iteration improved on the last; this reference captures the converged form.
