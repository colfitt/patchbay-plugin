---
phase: 03-patchbay-research-with-tiered-fetch
plan: 03
subsystem: equipboard-source-class
tags: [patchbay-research, source-class, equipboard, knowledge-graph, artist_usage, cross_ref, external_resource, cloudflare-block, meta-aggregator, beautifulsoup, html-parser]

# Dependency graph
requires:
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 01
    provides: empty REGISTRY skeleton, source-class three-callable contract, scripts/fetch_tier1.py shared fetcher, scripts/log_failure.classify_reason mapping cloudflare-block to (cloudflare-block, 2), scripts/write_chunk.py append-only writer
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 02
    provides: idempotent self-registration tail-snippet pattern (`if _self not in _REGISTRY: _REGISTRY.append(_self)`), single-line read-modify-write append idiom for __init__.py, test-harness pattern (research-root on sys.path + reload-both-modules for self-registration test)
provides:
  - skills/patchbay-research/source_classes/equipboard.py — Equipboard source class (match_url, fetch_tier1, parse_to_chunks) self-registering into REGISTRY
  - skills/patchbay-research/source_classes/__init__.py — single-line append `from . import equipboard` (read-modify-write preserves Plan 01's scaffold AND Plan 02's reddit append)
  - skills/patchbay-research/references/source-class-equipboard.md — reference doc covering URL pattern, Cloudflare expectation, chunk-type mapping, chunk-ID format, security mitigations, worked example per emitted type, UI layer notes
  - skills/patchbay-research/scripts/test_equipboard.py — 11 pytest cases (acceptance contract)
  - skills/patchbay-research/scripts/fixtures/equipboard_sample.html — minimal real-shaped item page (description, 2 artist blocks w/ + w/o quote, used-with list, similar-in-category list)
affects: [03-04-youtube-source-class, 03-05-review-failures, 04-citation-tracking]

# Tech tracking
tech-stack:
  added: []  # beautifulsoup4 already installed by Plan 01; html.parser is stdlib
  patterns:
    - "BeautifulSoup with `html.parser` (stdlib backend) — XXE-immune by construction since the stdlib parser does not resolve external entities"
    - "Defensive selector strategy per landmark: class-specific selector first, then heading-text fallback, then graceful skip (no error)"
    - "Verbatim quote extraction by longest-text-node threshold (>= 80 chars). Sub-threshold text collapses into `summary` so RESEARCH-08's 'verbatim quotes when present' contract is honored without inventing quotes"
    - "Two-pass artist-block processing: emit artist_usage chunks first, capture (block, yt_urls, chunk_id) triples, then walk triples to emit external_resource chunks with citing_chunk_ids pointing back at the parent artist_usage chunk's id"
    - "Idempotency-guarded self-registration (`if _self not in _REGISTRY`) — copied verbatim from Plan 02's reddit.py per the pattern Plan 02 established"
    - "Single-line read-modify-write append to source_classes/__init__.py — commutative with Plans 02 (already landed) and Plan 04 (pending). Scaffold + reddit's append preserved verbatim."

key-files:
  created:
    - skills/patchbay-research/source_classes/equipboard.py
    - skills/patchbay-research/references/source-class-equipboard.md
    - skills/patchbay-research/scripts/test_equipboard.py
    - skills/patchbay-research/scripts/fixtures/equipboard_sample.html
  modified:
    - skills/patchbay-research/source_classes/__init__.py

key-decisions:
  - "VERBATIM_QUOTE_MIN_CHARS = 80 — short text in an artist block (e.g., 'Roles: Guitarist') is collapsed into `summary` rather than misrepresented as a quote. 80 chars is comfortably longer than any role-list or one-line attribution, but well within a single sentence of reviewer commentary."
  - "External_resource chunks live AFTER artist_usage chunks in emit order — necessary because `citing_chunk_ids` must reference an already-emitted artist_usage id. Two-pass walk captures (block, yt_urls, chunk_id) triples on the first pass and produces external_resource chunks on the second pass."
  - "`verification_type` on artist_usage is derived heuristically from in-block evidence (presence of YouTube URL -> 'youtube'; 'interview' substring -> 'interview'; 'photo' / 'pedalboard' / 'Instagram' -> 'photo'; else 'unknown'). Falsifiable from the DOM, no external lookup."
  - "`from_gear` on cross_ref chunks comes from `gear_ctx.item` (e.g., 'Chase Bliss Audio Clean'), not from the page H1. The gear context is the load-bearing truth — the page H1 can be cosmetically rewritten by EB editors."
  - "Provenance.section uses DOM anchor strings (`#artist-<slug>`, `#used-with`, `#similar-in-category`, `description`) — the future UI helper can compose `provenance.url + provenance.section` into a deep_link without a schema change."
  - "BeautifulSoup uses `html.parser` (stdlib) NOT `lxml` — keeps dependencies minimal AND immune to XXE/billion-laughs (T-03-15/T-03-18 mitigations baked into the parser choice)."

patterns-established:
  - "Two-pass parse for citing_chunk_ids: any chunk type whose `citing_chunk_ids` field references another chunk MUST emit AFTER the cited chunk. Two-pass collection of (cited_chunk_id, derived_data) tuples then a second walk to emit the citing chunks. Plan 04 will hit this same constraint for YouTube `external_resource` enrichment via `update_chunk_field`."
  - "Defensive DOM-selector fallback: try the conventional class selector first, then a heading-text-substring search, then graceful skip. Equipboard's class names change occasionally per spike findings — the parser must not be brittle on a single CSS class."
  - "Source-class chunks set `tier_used` from `fetch_result.get('tier', 1)` so Plan 05's tier-2/3 callers can pass the actual tier without modifying parse_to_chunks. The parser is tier-agnostic."

requirements-completed: [RESEARCH-08]
requirements-partial: [RESEARCH-01]

# Metrics
duration: 5min
completed: 2026-05-16
---

# Phase 03 Plan 03: Equipboard source class Summary

**Shipped the meta-aggregator source class — `equipboard.py` parses Equipboard item-page HTML into the four knowledge-graph chunk types (`text` for the description, `artist_usage` per artist block with verbatim quotes when present, `cross_ref` for the `used_with` rollup and the `similar_in_category` list, and `external_resource` for YouTube URLs found inside artist blocks with citing_chunk_ids backlinking to the parent artist_usage chunk). The module self-registers into REGISTRY via the idempotent tail snippet established by Plan 02; `__init__.py` was modified by single-line read-modify-write append, preserving both Plan 01's scaffold and Plan 02's reddit append. RESEARCH-08 satisfied; ready for tier-2 (Claude_in_Chrome) escalation to drive the parser against live Equipboard DOM once Plan 05 ships.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-16T01:59:21Z
- **Completed:** 2026-05-16T02:03:51Z
- **Tasks:** 2 (Task 1 TDD red→green; Task 2 docs)
- **Files created:** 4
- **Files modified:** 1 (`__init__.py` — single-line append)

## Accomplishments

- **Equipboard chunk-type mapping wired end-to-end.** Against the captured HTML fixture: 1 `text` + 2 `artist_usage` (one with verbatim quote, one without) + 1 `cross_ref(used_with)` + 1 `cross_ref(similar_in_category)` + 1 `external_resource(youtube)` = the full knowledge-graph shape required by RESEARCH-08.
- **Self-registration pattern proven at second plug-in.** `equipboard.py` ends with the documented idempotent tail snippet (copy of Plan 02's exact form) and `__init__.py` carries Plan 01's scaffold + Plan 02's reddit append + Plan 03's equipboard append — all three lines present, no clobbering. Plan 04 (YouTube) can land independently with its own single-line append.
- **Five threat-register mitigations land in code.** T-03-13 (scheme guard before host), T-03-14 (exact-host set membership), T-03-15 (html.parser — XXE structurally impossible), T-03-16 (JSON-encoded chunks, no eval), T-03-17 (URL scheme re-validation post-regex). Each testable via the matching pytest case.
- **All 11 named acceptance tests pass.** First GREEN run was clean — the Plan 02 patterns (sys.path insertion, monkeypatch via `patch.object`, fixture-based parser tests, reload-both-modules for self-registration) transferred without surprises.
- **Full research suite green (35/35 tests):** Plan 01's 12 core tests + Plan 02's 12 reddit tests + Plan 03's 11 equipboard tests, no regressions.
- **Reference doc covers the full surface.** URL pattern table, Cloudflare expectation with classify_reason mapping table, chunk-type mapping table, chunk-ID format table, why-meta-aggregator section, one JSON example per emitted chunk type, security-mitigation table, and a `## UI layer notes` section (per user memory rule) covering per-artist deep links, artist_usage rendering, reviewer attribution surfacing, cross_ref gear-graph affordances, tier-of-origin badge, and external_resource cross-linking for Plan 04 enrichment.

## Task Commits

Each task committed atomically (TDD: RED test commit → GREEN feat commit):

1. **Task 1 RED: failing test_equipboard.py + fixture** — `d52fccb` (test)
2. **Task 1 GREEN: equipboard.py source class + registry append** — `e36a49f` (feat)
3. **Task 2: source-class-equipboard.md reference doc** — `a88d424` (docs)

**Plan metadata** (this SUMMARY + STATE + ROADMAP + REQUIREMENTS): added in the closing docs commit.

## Files Created/Modified

- `skills/patchbay-research/source_classes/equipboard.py` — Equipboard source class. Exports `match_url`, `fetch_tier1`, `parse_to_chunks`. Self-registers with idempotency guard. ~395 lines including docstrings + security comments.
- `skills/patchbay-research/source_classes/__init__.py` — Modified by read-modify-write: appended exactly one line `from . import equipboard  # noqa: F401  (auto-registers via side effect)`. Plan 01's `REGISTRY: list = []` scaffold preserved verbatim; Plan 02's `from . import reddit` line preserved verbatim. Plan 04 can append `from . import youtube` (and eventually `from . import generic`) without conflict.
- `skills/patchbay-research/references/source-class-equipboard.md` — Reference doc (~225 lines): URL pattern table, Cloudflare expectation, chunk-type mapping, chunk-ID format, why-meta-aggregator section, one JSON example per emitted chunk type, security-mitigation table, UI layer notes.
- `skills/patchbay-research/scripts/test_equipboard.py` — 11 pytest cases per the plan's acceptance criteria. Reuses Plan 02's harness pattern (sys.path insertion, monkeypatch via `patch.object`, fixture-based parser tests, reload-both-modules for self-registration).
- `skills/patchbay-research/scripts/fixtures/equipboard_sample.html` — Real-shaped Equipboard item page: description paragraph, two artist-usage sections (one with a verbatim quote + YouTube link, one with photo-evidence only), a "Used With" list of 3 items, a "Similar in Compressor Effects Pedals" top-3 list.

## Decisions Made

| Decision | Rationale |
|---|---|
| `VERBATIM_QUOTE_MIN_CHARS = 80` | Short text in an artist block (e.g., "Roles: Guitarist", a one-line attribution) is collapsed into `summary` rather than misrepresented as a quote. 80 chars is comfortably longer than any role-list or one-line attribution, but well within a single sentence of reviewer commentary. |
| External_resource chunks emit AFTER artist_usage chunks | `citing_chunk_ids` must reference an already-emitted artist_usage id. Two-pass walk: first pass captures `(block, yt_urls, chunk_id)` triples while emitting artist_usage chunks; second pass walks triples and emits external_resource chunks with the captured ids. |
| `verification_type` is heuristic, not external | Derived from in-block evidence (presence of YouTube URL → `youtube`; "interview" substring → `interview`; "photo"/"pedalboard"/"Instagram" → `photo`; else `unknown`). No external lookup, no LLM call — falsifiable from the DOM alone. |
| `from_gear` from `gear_ctx.item`, not page H1 | Gear context is the load-bearing truth: the user invokes `/patchbay:research <gear>` and the brand+item name is authoritative. EB's page H1 can be cosmetically rewritten by editors and would drift. |
| `provenance.section` carries the DOM anchor string | `#artist-<slug>` / `#used-with` / `#similar-in-category` / `description`. A future UI helper composes `provenance.url + provenance.section` into a deep_link without a schema change. |
| BeautifulSoup with `html.parser` (stdlib), NOT `lxml` | Plan-level constraint per the threat register: html.parser is immune to XXE (T-03-15) and billion-laughs (T-03-18) because it doesn't process external entities. Keeps deps minimal. |
| Defensive multi-selector fallback per landmark | Try class selector first, then heading-text substring, then graceful skip. EB class names change occasionally (per spike-findings web-scraping.md). |

## Deviations from Plan

None. The plan's contract was precise enough that the implementation landed without auto-fix bugs or scope-creep. The Plan 02 patterns (sys.path insertion in tests, idempotent self-registration tail snippet, single-line read-modify-write append) transferred verbatim. No deviations to record.

The plan's `<verification>` block mentions "9 pytest cases" but `<acceptance_criteria>` lists 11; the implementation honored the 11-case version (the source of truth for acceptance) and all 11 pass. This is a minor doc-drift inside the plan, not an implementation deviation. Flagged here for any future planner doing a doc-consistency pass.

## Issues Encountered

None. No environment setup required — `beautifulsoup4` was already installed by Plan 01. The stdlib `html.parser` backend is bundled with Python; the `bs4` package imports it via `BeautifulSoup(body, "html.parser")`.

The `python` binary is not on PATH in this environment (`python3` is); ran `python3 -m pytest …` instead. Not a deviation; an environment fact mirrored from Plan 01's setup.

## User Setup Required

None for Plan 03 itself.

**For end-to-end Equipboard ingestion to work, Plan 05 (`--review-failures`) is required:** tier-1 fetches against `equipboard.com` return 403 + Cloudflare body. The user reviews `failures.log` and escalates each Equipboard URL to tier 2 (Claude_in_Chrome — requires the user's Chrome extension to be installed and connected per spike 003b). Tier-2 capture pipes through `parse_to_chunks` with `fetch_result["tier"] = 2` and produces the same chunk shapes documented here.

## Threat Flags

None. Every file touched in this plan is in-scope for the plan's `<threat_model>` and all five mitigations (T-03-13 through T-03-17) land in code with matching test cases. The threat register's accepted-risk row (T-03-18, HTML billion-laughs) is structurally mitigated by the parser choice; no new surface introduced.

## Interface Contract for Plan 04 (YouTube) and Plan 05 (Review-Failures)

### Plan 04 (YouTube):

1. **Same self-registration tail.** Copy verbatim from `equipboard.py` (which copied verbatim from `reddit.py`):
   ```python
   from . import REGISTRY as _REGISTRY  # noqa: E402
   _self = sys.modules[__name__]
   if _self not in _REGISTRY:
       _REGISTRY.append(_self)
   ```
2. **Single-line read-modify-write append to `__init__.py`:** `from . import youtube`. Plans 02 and 03 are commutative with this; Plan 04 simply adds a third line. If a generic fallback module is later added, it MUST be appended LAST.
3. **Update_chunk_field is the right primitive for YouTube enrichment of EB chunks.** When Plan 04 ingests a YouTube URL that already appears as an `external_resource` chunk emitted by this plan (recognized by `content.url`), it should use `scripts.write_chunk.update_chunk_field` to fill the blank `creator` (already populated by EB but verify), `title`, `updated` fields rather than emit a new chunk. The `citing_chunk_ids` backlink is already in place.

### Plan 05 (`--review-failures`):

1. **Tier-2 (Claude_in_Chrome) is the default escalation for Equipboard.** Plan 01's `classify_reason` maps the 403 + `"Just a moment..."` body to `("cloudflare-block", 2)`. The interactive flow should highlight tier 2 as the default suggested action for every Equipboard failure.
2. **Tier-2 success path: pass `fetch_result["tier"] = 2` to `equipboard.parse_to_chunks`.** The parser is tier-agnostic — every emitted chunk gets `tier_used: fetch_result.get("tier", 1)`. Tier-3 (computer-use + vision) success follows the same shape with `tier = 3`.
3. **`mcp__Claude_in_Chrome__list_connected_browsers` precheck before tier 2.** If `[]`, the extension is not connected. Surface install instructions; do not fall through to tier 1 retry (Cloudflare won't budge) or silent failure. Spike 003c documented the failure mode; spike 003b documented the install + happy-path validation.
4. **Tier-2 capture pattern (from spike 003b):** `browser_batch` for navigate+wait+screenshot, then `get_page_text` returns the structured DOM string. Wrap it into `fetch_result = {"status": 200, "body": <html>, "url_attempted": <url>, "tier": 2, ...}` and call `equipboard.parse_to_chunks(fetch_result, gear_ctx)`.

## Next Phase Readiness

- **Plan 04 (YouTube) can start immediately.** The registry pattern is proven for a second source class; the tier_used-from-fetch_result contract is ready for tier-2/3 callers; the citing_chunk_ids two-pass pattern is documented for any future cross-chunk-reference type.
- **Plan 05 (`--review-failures`) has a complete consumer story for Equipboard chunks.** classify_reason mapping is locked, suggested escalation defaults are documented, parse_to_chunks is tier-agnostic.
- **No blockers.** No outstanding schema questions, no auth gates, no spike findings to chase.
- **One thing to watch in Plan 04 / 05:** the two-pass emit pattern (chunks with `citing_chunk_ids` come AFTER cited chunks) is a load-bearing invariant. Plan 04 will hit the same constraint if YouTube `multimodal_segment` chunks ever cite `transcript` chunks (or vice versa).

## Self-Check: PASSED

Verification (all from the plan's `<verify>` lines + acceptance criteria):

- FOUND: skills/patchbay-research/source_classes/equipboard.py
- FOUND: skills/patchbay-research/source_classes/__init__.py (modified, scaffold + reddit append preserved)
- FOUND: skills/patchbay-research/references/source-class-equipboard.md
- FOUND: skills/patchbay-research/scripts/test_equipboard.py
- FOUND: skills/patchbay-research/scripts/fixtures/equipboard_sample.html
- FOUND commits: d52fccb (Task 1 RED), e36a49f (Task 1 GREEN), a88d424 (Task 2 docs)
- pytest test_equipboard.py: 11 passed, 0 failed
- pytest full research suite: 35 passed (12 core + 12 reddit + 11 equipboard), 0 failed, no regressions
- grep `REGISTRY: list = []` in source_classes/__init__.py: present (Plan 01 scaffold preserved)
- grep `from . import reddit` in source_classes/__init__.py: present (Plan 02 append preserved)
- grep `from . import equipboard` in source_classes/__init__.py: present (Plan 03 single-line append landed)
- grep `artist_usage` / `used_with` / `similar_in_category` / `cloudflare-block` / `eb-<slug>` / `## UI layer notes` / `external_resource` in source-class-equipboard.md: all present

---
*Phase: 03-patchbay-research-with-tiered-fetch*
*Completed: 2026-05-16*
