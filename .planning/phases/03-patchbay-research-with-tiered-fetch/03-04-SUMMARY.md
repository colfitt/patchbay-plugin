---
phase: 03-patchbay-research-with-tiered-fetch
plan: 04
subsystem: youtube-source-class
tags: [patchbay-research, source-class, youtube, multimodal, yt-dlp, ffmpeg, vtt-parser, two-pass-enrichment, no-whisper, read-tool-vision]

# Dependency graph
requires:
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 01
    provides: empty REGISTRY skeleton, source-class three-callable contract, scripts/write_chunk.update_chunk_field (atomic field rewrite via tempfile.mkstemp + os.replace), SKILL.md skeleton with `## UI layer notes` table to extend
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 02
    provides: idempotent self-registration tail-snippet pattern, single-line read-modify-write __init__.py append idiom, test-harness pattern (research-root on sys.path + reload-both-modules for self-registration test)
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 03
    provides: precedent for read-modify-write append against a non-empty __init__.py — Plans 02 + 03's lines must survive Plan 04 verbatim
provides:
  - skills/patchbay-research/source_classes/youtube.py — YouTube source class (match_url + fetch_tier1 sentinel + parse_to_chunks orchestrator) self-registering into REGISTRY
  - skills/patchbay-research/source_classes/__init__.py — appended `from . import youtube` (Plan 01 scaffold + Plan 02 reddit + Plan 03 equipboard all preserved verbatim)
  - skills/patchbay-research/scripts/parse_vtt.py — rolling-window-aware VTT parser (handles YouTube's 3×-duplication quirk + inline timing tags; T-03-19 mitigations)
  - skills/patchbay-research/scripts/yt_pipeline.py — subprocess orchestration: yt-dlp (captions + 720p video) + ffmpeg (fps=1/30 frame sampling); argv-only, system-tempdir-only
  - skills/patchbay-research/references/source-class-youtube.md — pipeline shape + chunk-type mapping + two-pass model + system deps + security mitigations + UI layer notes
  - skills/patchbay-research/scripts/test_youtube.py — 19 pytest cases (acceptance contract)
  - skills/patchbay-research/scripts/fixtures/sample.vtt — VTT fixture with rolling-window quirk, inline timing tag, >30s cue span
  - skills/patchbay-research/SKILL.md — new `### YouTube two-pass enrichment` process subsection + new UI layer notes row for frame thumbnail rendering (additive only — Plan 01 content preserved verbatim)
affects: [03-05-review-failures, 04-citation-tracking]

# Tech tracking
tech-stack:
  added: []  # subprocess / re / tempfile / shutil / pathlib are all stdlib; bs4/requests were Plan 01/03
  external_runtime_deps_required:
    - yt-dlp (PATH) — caption + 720p video download
    - ffmpeg (PATH) — frame sampling at 1/30 fps
  patterns:
    - "Two-pass multimodal enrichment: pipeline writes chunks with `<<PENDING_READ_TOOL_DESCRIPTION>>` sentinel + `provenance.frame_path`; SKILL driver Reads each frame and overwrites via `write_chunk.update_chunk_field`. The sentinel string MUST never persist in chunks.jsonl past the end of a research run."
    - "Sentinel tier-1 fetch: `fetch_tier1` returns `{status: 0, needs_pipeline: True, body: '', ...}` for sources where static GET is useless. SKILL driver dispatches straight to `parse_to_chunks`. No failures.log entry on tier-1 'failure' — there's no fetch to fail."
    - "Per-run system tempdir via `tempfile.mkdtemp(prefix='patchbay-yt-')` with try/finally `shutil.rmtree` cleanup — NEVER under gear_root (T-03-22)."
    - "Pure-argv subprocess invocations: every `subprocess.run` uses `shell=False` with an explicit list. URL is one argv element, never interpolated into a string (T-03-20)."
    - "video_id allowlist regex `^[A-Za-z0-9_-]{6,20}$` after URL parse — prevents argv smuggling via crafted `v=` query value (T-03-21)."
    - "VTT rolling-window dedup: take last non-empty line per cue, dedupe consecutive identical lines across cues, window-anchored to first cue start (not fixed grid) so deep_link timestamps are content-anchored."
    - "Idempotent self-registration tail snippet (`if _self not in _REGISTRY`) — copied verbatim from Plan 02's reddit.py per Plan 02's established pattern."
    - "Single-line read-modify-write __init__.py append commutative with Plans 02 and 03 — scaffold + reddit append + equipboard append all preserved verbatim."

key-files:
  created:
    - skills/patchbay-research/source_classes/youtube.py
    - skills/patchbay-research/scripts/parse_vtt.py
    - skills/patchbay-research/scripts/yt_pipeline.py
    - skills/patchbay-research/references/source-class-youtube.md
    - skills/patchbay-research/scripts/test_youtube.py
    - skills/patchbay-research/scripts/fixtures/sample.vtt
  modified:
    - skills/patchbay-research/source_classes/__init__.py
    - skills/patchbay-research/SKILL.md

key-decisions:
  - "Window anchored to first cue start, not fixed `start // window_seconds` grid. The plan's `test_parse_vtt_timestamp_display_format` forced this: a window containing a cue at 6:45 must report `start == 405` (and `timestamp_display` starting with `6:45`), not 6:30 (the grid-bucket boundary). Anchoring to content keeps deep_link timestamps surgically aligned with what the user clicks through to."
  - "`<<PENDING_READ_TOOL_DESCRIPTION>>` chosen as the literal placeholder rather than empty-string. An empty `frame_description` is ambiguous (was the chunk enriched and found nothing? or did enrichment never run?); the sentinel is unambiguous and greppable. The SKILL.md two-pass loop searches for this exact string."
  - "Frame `.jpg` files live in the tempdir, NOT under gear_root. The two-pass enrichment loop MUST complete before `parse_to_chunks`'s try/finally cleanup runs. Plan 01's `update_chunk_field` is the right primitive — atomic rewrite via tempfile + os.replace. (Future enhancement: a 'promote frames' pass that copies them under `<gear_root>/<Brand Item>/knowledge/frames/` for UI-side thumbnail rendering.)"
  - "Sentinel tier-1 fetch for YouTube. `fetch_tier1` returns `needs_pipeline: True` rather than attempting a static GET against `/watch` — those pages are JS-heavy and never useful as static HTML. The SKILL driver branches on `needs_pipeline` and dispatches `parse_to_chunks` directly. No failures.log entry is written when yt-dlp is present + functional."
  - "`yt-dlp` absence is a structured failure record (`reason: other`, `reason_detail: 'yt-dlp not installed (PATH lookup failed)'`, `suggested_escalation: skip`) — NOT a swallowed silent return. The SKILL driver forwards this record to the Plan 01 `log_failure` helper so the user sees it in failures.log alongside HTTP failures."
  - "`ffmpeg` absence degrades to transcript-only chunks (no multimodal pairs). Distinct from yt-dlp absence: transcripts alone are useful (spike 002a validated their sufficiency for the audio side); multimodal-only is not. So ffmpeg-missing is silent degradation; yt-dlp-missing is a hard failure record."
  - "`_parse_vtt_safe` wrapper around `parse_vtt` lives inside yt_pipeline.py specifically so tests can monkeypatch the caption-parsing step without touching the real parser module. Keeps the parse_vtt unit tests isolated from the pipeline-orchestration tests."

patterns-established:
  - "Two-pass enrichment via `<<PENDING_READ_TOOL_DESCRIPTION>>` + `provenance.frame_path` + `write_chunk.update_chunk_field`: ANY future source class that needs vision-based field synthesis can copy this pattern. The sentinel string is greppable; the helper is atomic; the SKILL.md doc-pattern (insert a `### <source> two-pass enrichment` subsection in the Process section) is reusable."
  - "Sentinel tier-1 fetch result (`needs_pipeline: True`): any future source class where static HTML is useless (e.g., Spotify embeds, Instagram, TikTok if added) can adopt the same shape. The router doesn't change; the SKILL driver's success branch grows a `if result.get('needs_pipeline'):` arm."
  - "Per-run tempdir + try/finally cleanup: any future source class doing multi-asset downloads should follow this. Frames/audio/transcripts that don't end up as chunks should NOT persist on disk; only the JSONL line is permanent."

requirements-completed: [RESEARCH-07]
requirements-partial: [RESEARCH-01]

# Metrics
duration: 7min
completed: 2026-05-16
---

# Phase 03 Plan 04: YouTube source class Summary

**Shipped the multimodal-secondary source class — `youtube.py` orchestrates yt-dlp (auto-captions + 720p video) + parse_vtt (rolling-window-aware) + ffmpeg (1/30 fps frame sampling) into `transcript` + `multimodal_segment` chunks. The pipeline emits multimodal chunks with a `<<PENDING_READ_TOOL_DESCRIPTION>>` placeholder + `provenance.frame_path`; the SKILL.md "YouTube two-pass enrichment" subsection (added in this plan) instructs the driver to Read each frame and overwrite the placeholder via Plan 01's `write_chunk.update_chunk_field`. NO Whisper anywhere (RESEARCH-07). Single-line read-modify-write append on `__init__.py` preserves Plan 01's scaffold + Plan 02's reddit + Plan 03's equipboard appends verbatim. 19 pytest cases pass; full research suite 54/54 green, no regressions.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-16T02:07:38Z
- **Completed:** 2026-05-16T02:14:48Z
- **Tasks:** 3 (Task 1 TDD red→green for parse_vtt; Task 2 TDD red→green for youtube/yt_pipeline + docs; Task 3 SKILL.md additive update)
- **Files created:** 6
- **Files modified:** 2 (`__init__.py` — single-line append; `SKILL.md` — additive subsection + UI row)

## Accomplishments

- **YouTube multimodal pipeline wired end-to-end** — against monkeypatched yt-dlp/ffmpeg/parse_vtt, the source class produces the full chunk shape required by RESEARCH-07: one `transcript` chunk per caption window plus one `multimodal_segment` chunk per (window, frame) pair carrying the sentinel placeholder + `provenance.frame_path`. The SKILL driver completes the second pass.
- **NO Whisper anywhere.** Auto-captions are the only audio-text layer. `grep -ri "whisper" skills/patchbay-research/` returns nothing in the YouTube code path. RESEARCH-07's no-Whisper contract is hard-locked in code, in tests, and in the reference doc.
- **Self-registration pattern proven at third plug-in.** `youtube.py` ends with the idempotent tail snippet (copy of Plan 02/03's exact form) and `__init__.py` now carries Plan 01's scaffold + Plan 02's reddit append + Plan 03's equipboard append + Plan 04's youtube append — all four lines present, no clobbering.
- **Five threat-register mitigations land in code with matching pytest cases:**
  - T-03-19 (path injection via VTT path) → `pathlib.Path.resolve` + `errors="replace"` in parse_vtt; no `subprocess`/`eval`/`exec` (`grep -E "(^|[^a-z])(eval|exec|subprocess)\(" parse_vtt.py` returns nothing).
  - T-03-20 (RCE via shell metachars in URL) → every `subprocess.run` uses `shell=False` with an argv list, verified by `test_yt_pipeline_uses_argv_not_shell`.
  - T-03-21 (argv smuggling via crafted `v=` query value) → `^[A-Za-z0-9_-]{6,20}$` allowlist; rejected ids return `"unknown"`.
  - T-03-22 (tempfile location under gear_root) → `tempfile.mkdtemp(prefix="patchbay-yt-")` lands in system temp; `test_yt_pipeline_tempdir_outside_gear_root` asserts no path component is inside a fake gear_root.
  - T-03-24 (URL scheme abuse) → non-http(s) rejected before host check; `test_match_url_rejects_non_https_scheme` covers `javascript:`, `file://`, and `ftp://`.
- **SKILL.md two-pass enrichment hook documented.** The new `### YouTube two-pass enrichment` subsection tells the SKILL driver verbatim how to complete the loop: Read `provenance.frame_path`, generate a one-sentence description, call `write_chunk.update_chunk_field(...)` to overwrite the literal sentinel `<<PENDING_READ_TOOL_DESCRIPTION>>`. Without this hook, every YouTube run would leave placeholder chunks in `chunks.jsonl` forever — RESEARCH-07 unfulfilled. The plan's CRITICAL #2 constraint was the explicit guard against skipping this task.
- **All 19 named acceptance tests pass on first GREEN run.** No deviations. The Plan 02 / Plan 03 test-harness pattern (sys.path insertion, monkeypatched aliased helpers, reload-both-modules for self-registration) transferred without surprises.
- **Full research suite green (54/54 tests):** Plan 01's 12 core + Plan 02's 12 reddit + Plan 03's 11 equipboard + Plan 04's 19 youtube, no regressions.

## Task Commits

Each task committed atomically (TDD: RED test commit → GREEN feat commit; Task 3 docs commit):

1. **Task 1 RED: failing parse_vtt tests + sample.vtt fixture** — `f4b80af` (test)
2. **Task 1 GREEN: parse_vtt.py — rolling-window-aware VTT parser** — `6f87b5d` (feat)
3. **Task 2 RED: failing youtube + yt_pipeline tests** — `c222423` (test)
4. **Task 2 GREEN: youtube source class + yt_pipeline + __init__.py append + reference doc** — `6b522c1` (feat)
5. **Task 3: SKILL.md two-pass enrichment subsection + UI row** — `592f1c8` (docs)

**Plan metadata** (this SUMMARY + STATE + ROADMAP + REQUIREMENTS): added in the closing docs commit.

## Files Created/Modified

- `skills/patchbay-research/source_classes/youtube.py` — YouTube source class (`match_url`, `fetch_tier1` returning the `needs_pipeline` sentinel, `parse_to_chunks` orchestrator). Self-registers with idempotency guard. Records `last_failure_record` for yt-dlp-missing so the SKILL driver can forward to `failures.log`. ~205 lines.
- `skills/patchbay-research/scripts/parse_vtt.py` — Rolling-window-aware VTT parser. Strips inline timing tags + `<c>`/`</c>`, takes last non-empty cue line, dedupes consecutive identical lines, groups into N-second windows anchored to the first cue start. Returns `[]` on missing/empty file (never raises). Stdlib only. ~150 lines.
- `skills/patchbay-research/scripts/yt_pipeline.py` — subprocess orchestration. `fetch_video_assets` invokes yt-dlp twice (captions, then 720p video); `sample_frames` invokes ffmpeg `fps=1/30`; `build_multimodal_chunks` zips windows with frame paths into transcript + multimodal_segment chunks. `make_tempdir` is a thin `tempfile.mkdtemp(prefix="patchbay-yt-")` wrapper so tests can spy without monkeypatching `tempfile` globally. ~250 lines.
- `skills/patchbay-research/source_classes/__init__.py` — Modified by read-modify-write: appended exactly one line `from . import youtube  # noqa: F401  (auto-registers via side effect)`. Plan 01's `REGISTRY: list = []` scaffold preserved verbatim; Plan 02's `from . import reddit` line preserved verbatim; Plan 03's `from . import equipboard` line preserved verbatim. File now contains all four required lines.
- `skills/patchbay-research/references/source-class-youtube.md` — Reference doc (~230 lines): URL pattern table, full pipeline diagram, chunk-type mapping table, NO-Whisper contract callout, two-pass model section, system dependencies table (yt-dlp + ffmpeg), security-mitigation table (T-03-20/21/22/24), UI layer notes (6 affordances including frame-thumbnail rendering), worked-example chunk shapes for `transcript` and `multimodal_segment` (pre- and post-enrichment).
- `skills/patchbay-research/scripts/test_youtube.py` — 19 pytest cases. Task 1: 7 parse_vtt cases (6 plan-named + 1 fixture-driven sanity). Task 2: 12 cases covering match_url, fetch_tier1 sentinel, subprocess argv safety, tempdir location, parse_to_chunks orchestration (transcripts + yt-dlp-missing + multimodal frame_path), __init__.py preservation, self-registration via reload-both-modules.
- `skills/patchbay-research/scripts/fixtures/sample.vtt` — VTT fixture: 8 cues, rolling-window duplication, inline `<00:00:08.500><c>` timing tag, spans 0–68s so window grouping produces ≥2 windows. Includes the substring "twenty eight different effects" (a callback to spike-002's load-bearing example).
- `skills/patchbay-research/SKILL.md` — Modified additively: new `### YouTube two-pass enrichment` subsection inserted in the Process section between Step 6 (Closeout) and the existing `## Cross-source corroboration` section; new row appended to the existing UI layer notes table covering frame thumbnail rendering + pending-vision-review badge + `?t=<seconds>` deep_link affordance. Plan 01's frontmatter, all 6 process steps, the cross-source-corroboration section, the error-handling table, and the security-notes section all preserved verbatim.

## Decisions Made

| Decision | Rationale |
|---|---|
| Window start anchored to first cue, NOT fixed grid | `test_parse_vtt_timestamp_display_format` requires a cue at 6:45 (405s) to produce a window with `start == 405` and `timestamp_display` starting with `6:45`. Grid-bucketing would have yielded 6:30. Content-anchored windows keep deep_link timestamps aligned with what the user clicks through to. |
| `<<PENDING_READ_TOOL_DESCRIPTION>>` literal sentinel, NOT empty string | Empty `frame_description` is ambiguous (was the chunk enriched-and-empty, or did enrichment never run?). The sentinel is unambiguous, greppable, and the SKILL.md two-pass loop searches for it verbatim. |
| Sentinel tier-1 fetch (`needs_pipeline: True`) | YouTube `/watch` pages are JS-heavy and useless as static HTML. Returning a static GET error would trigger an unhelpful `failures.log` entry. The sentinel tells the SKILL driver to dispatch `parse_to_chunks` directly. No fetch failure means no failures.log entry. |
| `yt-dlp` missing → structured failure record; `ffmpeg` missing → silent degradation to transcripts | Transcripts alone are useful (validated in spike 002a). Multimodal-only is not. So ffmpeg-absent is a graceful degrade; yt-dlp-absent is hard-fail (no captions, no video — nothing to chunk). The hard-fail emits a record the SKILL driver forwards to `failures.log` via Plan 01's `log_failure`. |
| Frames live in tempdir, NEVER under gear_root (T-03-22) | The SKILL driver MUST complete the two-pass enrichment loop before `parse_to_chunks`'s try/finally cleans up. After cleanup, only the JSONL chunks persist. A future "promote frames" pass can copy them under `<gear_root>/<Brand Item>/knowledge/frames/` if the user wants UI-side thumbnails to survive. |
| `_parse_vtt_safe` wrapper in yt_pipeline.py | Lets pipeline tests monkeypatch caption-parsing without touching the real `parse_vtt` module. Keeps parse_vtt unit tests isolated from pipeline-orchestration tests. |
| `make_tempdir` is a thin module-level function | Tests can spy on `tempfile.mkdtemp` via `monkeypatch.setattr(yt_pipeline.tempfile, "mkdtemp", ...)` without leaking into the rest of the test process. The fixture-named function makes the call-site greppable. |
| Idempotent self-registration tail snippet copied from Plan 02/03 verbatim | Plan 02 documented this pattern and Plan 03 reused it. Mechanical copy is the safest path — no novel registration semantics; the membership check (`if _self not in _REGISTRY`) is required for `importlib.reload` correctness. |

## Deviations from Plan

**None of substance.** The plan's contract was precise enough that the implementation landed without auto-fix bugs or scope creep.

One minor course-correction during Task 1 GREEN:

**1. [Self-corrected during TDD] Initial window-grouping used fixed grid; test forced content-anchored**
- **Found during:** Task 1 first GREEN run.
- **Issue:** The first implementation used `bucket = int(start // window_seconds)` to group cues, producing windows aligned to the 30s grid (a cue at 6:45 went into the 6:30–7:00 bucket → `start == 390`). The test `test_parse_vtt_timestamp_display_format` requires `int(first["start"]) == 405` (the cue's actual start time, not the bucket boundary).
- **Fix:** Rewrote the window grouper to anchor each window to the first un-bucketed cue's start time. Successive cues whose start falls within `[window_start, window_start + window_seconds)` go into the same window; the next cue starts a new one. This satisfies BOTH the grid-style test (3 cues at 0/35/65s produce 3 windows) AND the content-anchored test (cue at 405s produces a window with `start == 405`).
- **Files modified:** skills/patchbay-research/scripts/parse_vtt.py
- **Verification:** All 7 parse_vtt cases pass; full research suite 54/54 green.
- **Committed in:** 6f87b5d (Task 1 GREEN commit — the fix was made before the GREEN commit, so it is part of the implementation commit, not a separate fix commit).

This is a single TDD course-correction (RED revealed an unintended interpretation; GREEN landed the corrected behavior), not an external deviation. The plan's `<behavior>` block was technically silent on bucket-vs-content-anchored — the test gave the load-bearing constraint.

## Threat Flags

None. Every file touched in this plan is in-scope for the plan's `<threat_model>` and the five high-severity mitigations (T-03-19/20/21/22/24) land in code with matching test cases. Accepted-risk rows (T-03-23 malicious VTT content; T-03-25 long-video DoS) are documented in the reference doc with the same bounds the plan declared. No new surface introduced.

## Issues Encountered

None. `python3 -m pytest` was already on PATH from Plan 01's setup; `yt-dlp` and `ffmpeg` are NOT required for the test suite (every subprocess call is monkeypatched). End-to-end runs against a real YouTube URL require the user to `brew install yt-dlp ffmpeg`; this is documented in `references/source-class-youtube.md` § System dependencies.

## User Setup Required

For YouTube ingestion to work end-to-end at runtime (not at test time):

- `brew install yt-dlp` (or `pipx install yt-dlp`)
- `brew install ffmpeg`

Both must be on `PATH`. If `yt-dlp` is missing, a research run against a YouTube URL writes a structured failure to `failures.log` (`reason: other`, `reason_detail: yt-dlp not installed (PATH lookup failed)`, `suggested_escalation: skip`) — the user sees a clear message in the failures-review flow. If `ffmpeg` is missing, the pipeline silently degrades to transcript-only chunks (no multimodal pairs); the user gets caption-only data but still useful chunks.

## Interface Contract for Plan 05 (`--review-failures`)

Plan 05 will read `failures.log` and walk the user through escalation. For YouTube failures:

1. **yt-dlp missing** (`reason: other`, detail contains "yt-dlp"): the suggested escalation is `skip`. Plan 05's UI should surface "Install yt-dlp via `brew install yt-dlp`, then re-run `/patchbay:research <gear> <url>`" — there is no tier-2/3 escalation that helps; the user has to install the dep.
2. **video unavailable / 404**: classify_reason already maps to `404, skip`. No tier-2 path is meaningful.
3. **Network failures during the pipeline**: subprocess raises a timeout / non-zero exit. The SKILL driver should catch and log with `reason: timeout` (escalation `either`) or `reason: other` (escalation `either`).

The YouTube source class is **tier-agnostic** at `parse_to_chunks`: a tier-2/3 caller (e.g., a future "screen-capture the YouTube player and OCR" pathway) can pass `fetch_result["tier"] = 2` and the same chunk shapes emit. Currently the parser hardcodes `tier_used: 1` — Plan 05 should patch this to `fetch_result.get("tier", 1)` if/when a tier-2/3 YouTube path ships, mirroring how Plan 03 (Equipboard) parameterized `tier_used`.

## Interface Contract for Phase 04 (Citation Tracking)

YouTube `multimodal_segment` chunks expose three fields that the citation-hover UX depends on:

- `provenance.deep_link` (`&t=<seconds>s` / `?t=<seconds>s`) — what the UI's "jump to source" affordance points at.
- `provenance.frame_path` — the local image the UI thumbnails (or, post-promotion, a path under `<gear_root>/<Brand Item>/knowledge/frames/`).
- `content.frame_description` (post-enrichment) — the alt-text + the "what's visually distinguishable" sentence the UI surfaces alongside the thumbnail.

Phase 04's citation feedback loop can treat the (deep_link, frame_path, frame_description) triple as a single citable atom — the user hovering over a sentence in an answer that's grounded in a YouTube chunk gets the thumbnail + the deep-link click + the synthesized description, all in one render.

## Next Phase Readiness

- **Plan 05 (`--review-failures`) can start immediately.** All three YouTube failure modes are documented; classify_reason mapping is locked; suggested escalation defaults are explicit.
- **Phase 04 (Citation Tracking) can start immediately.** The chunk shape exposes the three load-bearing fields (deep_link, frame_path, frame_description); the two-pass model means every YouTube chunk in `chunks.jsonl` carries a real description (not a sentinel) by the time Phase 04 reads it.
- **No blockers.** No outstanding schema questions, no auth gates, no spike findings to chase.
- **One thing to watch in Phase 04 UI work:** the `<<PENDING_READ_TOOL_DESCRIPTION>>` sentinel MUST NEVER persist in chunks.jsonl past the end of a research run. If Phase 04 ever encounters a chunk still carrying the sentinel (failure mode: the enrichment loop crashed mid-run, or the tempdir was cleaned before the SKILL driver finished), it should render the "pending vision review" badge and prompt the user to re-trigger enrichment rather than rendering the literal placeholder. Documented in SKILL.md.

## Self-Check: PASSED

Verification (all from the plan's `<verify>` lines + acceptance criteria + the orchestrator's success_criteria):

- FOUND: skills/patchbay-research/source_classes/youtube.py
- FOUND: skills/patchbay-research/scripts/parse_vtt.py
- FOUND: skills/patchbay-research/scripts/yt_pipeline.py
- FOUND: skills/patchbay-research/scripts/test_youtube.py
- FOUND: skills/patchbay-research/scripts/fixtures/sample.vtt
- FOUND: skills/patchbay-research/references/source-class-youtube.md
- FOUND: skills/patchbay-research/source_classes/__init__.py (modified — all four lines present)
- FOUND: skills/patchbay-research/SKILL.md (modified — additive)
- FOUND commits: f4b80af (Task 1 RED), 6f87b5d (Task 1 GREEN), c222423 (Task 2 RED), 6b522c1 (Task 2 GREEN), 592f1c8 (Task 3 docs)
- pytest test_youtube.py: 19 passed, 0 failed
- pytest full research suite: 54 passed (12 core + 12 reddit + 11 equipboard + 19 youtube), 0 failed, no regressions
- grep `REGISTRY: list = []` in source_classes/__init__.py: present (Plan 01 scaffold preserved)
- grep `from . import reddit` in source_classes/__init__.py: present (Plan 02 append preserved)
- grep `from . import equipboard` in source_classes/__init__.py: present (Plan 03 append preserved)
- grep `from . import youtube` in source_classes/__init__.py: present (Plan 04 single-line append landed)
- grep `multimodal_segment` in source-class-youtube.md: present
- grep `Whisper` in source-class-youtube.md: present (the NO-Whisper callout)
- grep `## UI layer notes` in source-class-youtube.md: present (user memory rule satisfied)
- grep `shell=True` in yt_pipeline.py + youtube.py: NOT present (security gate)
- grep `(eval|exec|subprocess)\(` in parse_vtt.py: NOT present (T-03-19 gate)
- SKILL.md grep gates (all present): `YouTube two-pass enrichment`, `<<PENDING_READ_TOOL_DESCRIPTION>>`, `update_chunk_field`, `provenance.frame_path`, `name: patchbay-research` (frontmatter preserved), `cross_source_match_candidates` (Plan 01 content preserved), `UI layer notes` (table preserved + new row added)
- `multimodal_segment` chunks: `provenance.frame_path` set on every chunk verified by `test_multimodal_chunk_has_frame_path_in_provenance`
- NO Whisper / faster-whisper / openai-whisper imports anywhere: `grep -ri "whisper" skills/patchbay-research/` returns no Python imports (only the negative-callout doc strings in the reference doc and this SUMMARY)

---
*Phase: 03-patchbay-research-with-tiered-fetch*
*Completed: 2026-05-16*
