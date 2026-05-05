# Patchbay: Source Fetch Strategies

## General rules

- Save each fetched source to `<song-folder>/sources/<site>-<YYYY-MM-DD>.md`.
- Include frontmatter at top of each saved source file (see template below).
- Truncate body to 12,000 characters if larger; add a "... [truncated]" note.
- If a fetch fails or returns garbage HTML / binary / unrelated content: skip that source and note the skip inline. One bad source skipped > bad data included.
- Never let a single source failure abort the whole run.

## Source file frontmatter template

```yaml
---
url: <full URL>
fetched_at: <ISO 8601 datetime>
fetcher: <fetcher-name>
---
```

## Site strategies (highest confidence first)

### 1. Equipboard
Fetcher name: `equipboard-direct`

1. Construct URL: `https://equipboard.com/pros/<artist-slug>` where slug = artist name lowercased, spaces → hyphens (e.g., `jonny-greenwood`, `thom-yorke`).
2. `WebFetch` that URL.
3. If response is 403, Cloudflare challenge page, or CAPTCHA: fall back to `WebSearch "<artist> equipboard"` and WebFetch the top result URL.
4. Save as `sources/equipboard-<YYYY-MM-DD>.md`.

Signal: structured gear lists with brand/model. High confidence.

### 2. Premier Guitar
Fetcher name: `premier-guitar-rundown`

1. `WebSearch '"<artist>" "<song>" site:premierguitar.com'`
2. If no results: try `"<artist> rig rundown site:premierguitar.com"`.
3. `WebFetch` the top relevant result.
4. Save as `sources/premier-guitar-<YYYY-MM-DD>.md`.

Signal: rig rundown articles and video walkthroughs with hands-on gear detail.

### 3. Sound on Sound
Fetcher name: `sound-on-sound`

1. `WebSearch '"<artist>" "<song>" site:soundonsound.com'`
2. If no results: try `'"<artist>" site:soundonsound.com'`.
3. `WebFetch` top result.
4. Save as `sources/sound-on-sound-<YYYY-MM-DD>.md`.

Signal: "In The Studio" features and production breakdowns with recording context.

### 4. Tape Op
Fetcher name: `tapeop`

1. `WebSearch '"<artist>" site:tapeop.com'`
2. `WebFetch` top result.
3. Save as `sources/tapeop-<YYYY-MM-DD>.md`.

Signal: interview-format with detailed tracking / production notes. Occasionally vague on exact model numbers.

### 5. YouTube rig rundowns
Fetcher name: `youtube-rundown`

1. `WebSearch '"<artist>" "<song>" rig rundown site:youtube.com'` — or without `site:` filter if needed.
2. Identify top 2 YouTube video URLs from results.
3. For each: run `add-youtube <url>` (this CLI fetches the transcript and saves it as markdown).
4. Move or copy the output file into `sources/youtube-<video-id>-<YYYY-MM-DD>.md`.
5. **If `add-youtube` is not installed or errors:** skip YouTube sources entirely; append this note to `## Sources` in SongProfile.md:
   > "YouTube sources skipped — `add-youtube` CLI not installed. See Pedalxly `rust-tools/` for the tool."

### 6. General web fallback
Fetcher name: `web-fallback`

1. `WebSearch '"<artist>" "<song>" gear used recording signal chain'`
2. `WebFetch` top 2–3 results not already fetched above.
3. Save as `sources/web-<YYYY-MM-DD>.md` (combine multiple results into one file with a URL header per result).
4. Useful for: Reddit threads (r/guitarpedals, r/gearslutz), fan wikis, blog posts, interviews.

## Source priority / confidence

| Source | Confidence | Why |
|---|---|---|
| Equipboard | High | Structured musician-gear database |
| Premier Guitar | High | Journalist rig rundowns, hands-on |
| Sound on Sound | High | Detailed production features |
| Tape Op | Med–High | Interview-based; occasionally imprecise on model |
| YouTube rundowns | Med | Transcribed speech; imprecise at times |
| General web | Low–Med | Unvetted; useful for corroboration |

## Conflict handling

When two sources disagree on a gear claim, surface the conflict explicitly in `## Research`:

> "Pedal: DigiTech Whammy II ([equipboard-2026-05-05.md](sources/equipboard-2026-05-05.md)) vs. Whammy IV ([premier-guitar-2026-05-05.md](sources/premier-guitar-2026-05-05.md)) — see Corrections to resolve."

Do not pick a winner. Do not average. Let the user correct via `## Corrections`.
