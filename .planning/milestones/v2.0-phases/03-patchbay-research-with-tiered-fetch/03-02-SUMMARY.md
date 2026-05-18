---
phase: 03-patchbay-research-with-tiered-fetch
plan: 02
subsystem: reddit-source-class
tags: [patchbay-research, source-class, reddit, tier-1, json-cheap-path, self-registration, ssrf-mitigations]

# Dependency graph
requires:
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 01
    provides: empty REGISTRY skeleton, source-class three-callable contract, scripts/fetch_tier1.py shared fetcher, scripts/write_chunk.py append-only writer
provides:
  - skills/patchbay-research/source_classes/reddit.py — Reddit source class (match_url, fetch_tier1, parse_to_chunks) self-registering into REGISTRY
  - skills/patchbay-research/source_classes/__init__.py — single-line append `from . import reddit` (read-modify-write preserves Plan 01's `REGISTRY: list = []` scaffold)
  - skills/patchbay-research/references/source-class-reddit.md — reference doc with URL pattern, cheap-path rewrite, JSON-to-chunk mapping, chunk-ID format, escalation policy, UI layer notes
  - skills/patchbay-research/scripts/test_reddit.py — 12 pytest cases (acceptance contract)
  - skills/patchbay-research/scripts/fixtures/reddit_sample.json — minimal real-shaped Reddit response (1 OP + 3 comments, youtube + reverb URLs)
affects: [03-03-equipboard-source-class, 03-04-youtube-source-class, 03-05-review-failures]

# Tech tracking
tech-stack:
  added: []  # urllib.parse / json / re / sys are all stdlib
  patterns:
    - "Self-registering source-class module: ends with `_REGISTRY.append(sys.modules[__name__])` guarded by membership check (idempotent under importlib.reload)"
    - "Read-modify-write registry append: scan `__init__.py` for literal `from . import reddit`; only append if absent — commutative with Plans 03/04"
    - "Canonical `.json` URL rewrite: strip trailing slash THEN append `.json` to path (NEVER `/.json`); query + fragment preserved"
    - "Permalink reconstruction with `/r/` prefix gate (T-03-09) — falls back to input URL on tampered permalinks"
    - "External URL extractor: regex match → `urlparse` scheme re-validation → host-based youtube/article classification (T-03-10)"

key-files:
  created:
    - skills/patchbay-research/source_classes/reddit.py
    - skills/patchbay-research/references/source-class-reddit.md
    - skills/patchbay-research/scripts/test_reddit.py
    - skills/patchbay-research/scripts/fixtures/reddit_sample.json
  modified:
    - skills/patchbay-research/source_classes/__init__.py

key-decisions:
  - "Self-registration guarded by `if _self not in _REGISTRY` — idempotent under `importlib.reload`. Without this, test_reddit_self_registers_into_registry failed because reload-cycles silently re-append (or, in the seen failure mode, fail to re-append against a fresh REGISTRY because sys.modules was cached)."
  - "Test reloads BOTH `source_classes` AND `reddit` modules to simulate cold start — reloading the package alone resets REGISTRY to `[]` but does not re-run reddit.py's module body, leaving REGISTRY empty in the assertion. Fixed test, not implementation."
  - "Trailing-punctuation strip on extracted URLs (`.rstrip('.,;:!?')`) — common prose pattern is `... see https://example.com/foo.` and a naive regex captures the trailing dot, breaking the URL. Stripping is conservative; legitimate URLs don't end in these characters."
  - "`_shared_fetch_tier1` aliased import — lets tests monkeypatch the network call without colliding with this module's own `fetch_tier1`. Per the registry contract, the local `fetch_tier1` is the public callable."

patterns-established:
  - "Source-class self-registration tail snippet (idempotent variant): `from . import REGISTRY as _REGISTRY; _self = sys.modules[__name__]; if _self not in _REGISTRY: _REGISTRY.append(_self)`. Plans 03/04 should copy this exact form."
  - "Source-class test harness: monkeypatch the aliased `_shared_fetch_tier1` to inject fake responses; load a real-shaped fixture from `scripts/fixtures/<source>_sample.json` for parse_to_chunks tests."
  - "Reddit-specific: chunk IDs grounded on `data.id` from the JSON (Reddit-assigned post id), NOT parsed from the URL slug — the slug can be user-edited; the id is stable."

requirements-completed: [RESEARCH-06]

# Metrics
duration: 4min
completed: 2026-05-16
---

# Phase 03 Plan 02: Reddit source class Summary

**Shipped the first source-class plug-in to the registry built in Plan 01: a Reddit `.json`-cheap-path module that self-registers, matches `reddit.com/r/<sub>/comments/<id>` URLs with strict scheme/host/path guards, rewrites to the canonical `.json` path, parses the two-listing JSON into one OP chunk + one `comment_aggregate` + N `external_resource` chunks, and lands in `__init__.py` via a single-line read-modify-write append.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-16T01:51:55Z
- **Completed:** 2026-05-16T01:55:42Z
- **Tasks:** 2 (Task 1 TDD red→green; Task 2 docs)
- **Files created:** 4
- **Files modified:** 1 (`__init__.py` — single-line append)

## Accomplishments

- **Reddit cheap path is wired end-to-end** — `match_url` → `fetch_tier1` (rewriting to `.json`) → `parse_to_chunks` produces schema-conformant chunks ready to flow through `write_chunks` (which auto-populates `cross_source_match_candidates`). No tier-2/3 path needed for Reddit; the JSON endpoint is universally reachable.
- **Self-registration pattern proven at first plug-in** — `reddit.py` ends with the documented tail snippet (with an idempotency guard) and `__init__.py` carries exactly one `from . import reddit` line APPENDED to Plan 01's empty `REGISTRY: list = []` scaffold. Plans 03 and 04 can land independently with their own single-line appends.
- **All four threat-register mitigations land in code** — T-03-07 (non-http(s) schemes rejected before host check), T-03-08 (exact-host set membership, no substring), T-03-09 (permalink `/r/` prefix gate), T-03-10 (external URL scheme re-validation after regex match). Each is testable via the matching pytest case.
- **Twelve named acceptance tests pass on first GREEN run** — except for one (`test_reddit_self_registers_into_registry`) that exposed a test-correctness gap, not an implementation gap. Fix detailed under deviations.
- **Reference doc covers the full surface** — URL pattern, cheap-path rewrite (with edge cases for query + fragment), JSON-to-chunk mapping per type, chunk-ID stability rule, escalation policy, worked example per chunk type, and a UI layer notes section per user memory rule.

## Task Commits

Each task committed atomically:

1. **Task 1 RED: failing test_reddit.py + fixture** — `fb47523` (test)
2. **Task 1 GREEN: reddit.py source class + registry append** — `ee6ce8f` (feat)
3. **Task 2: source-class-reddit.md reference doc** — `b485af3` (docs)

**Plan metadata** (this SUMMARY + STATE + ROADMAP + REQUIREMENTS): added in the closing docs commit.

## Files Created/Modified

- `skills/patchbay-research/source_classes/reddit.py` — Reddit source class. Exports `match_url`, `fetch_tier1`, `parse_to_chunks`. Self-registers with idempotency guard. ~280 lines including docstrings + security comments.
- `skills/patchbay-research/source_classes/__init__.py` — Modified by read-modify-write: appended exactly one line `from . import reddit  # noqa: F401  (auto-registers via side effect)`. Plan 01's `REGISTRY: list = []` scaffold preserved verbatim. Plans 03/04 can append their own lines without conflict.
- `skills/patchbay-research/references/source-class-reddit.md` — Reference doc: URL pattern table, cheap-path rewrite rules, JSON-to-chunk mapping per type, chunk-ID format with stability rule, escalation policy table, worked example for each emitted type, UI layer notes (5 affordances), spike-findings citation.
- `skills/patchbay-research/scripts/test_reddit.py` — 12 pytest cases per the plan's acceptance criteria. Loads fixture, mocks `_shared_fetch_tier1` via `patch.object` for URL-rewrite verification.
- `skills/patchbay-research/scripts/fixtures/reddit_sample.json` — Real two-listing-shape Reddit response: 1 OP (id `abc123`, selftext mentions YouTube URL and "Rhett Shull"), 3 top-level comments with `body`/`author`/`ups` (87, 54, 31).

## Decisions Made

| Decision | Rationale |
|---|---|
| Self-registration is idempotent (`if _self not in _REGISTRY`) | Test reload cycles re-import the module; without the guard the same module appears in REGISTRY multiple times, breaking the `mod = route_url(url, REGISTRY)` invariant that the first match wins. |
| URL rewrite preserves query + fragment | A future caller might pass `https://reddit.com/r/x/comments/abc?sort=new` expecting `.json` to honor the sort. Canonical-path rewrite + query passthrough means the cheap path doesn't silently drop user intent. |
| Trailing-punctuation strip on extracted URLs | Prose like "see https://example.com/foo." captures the dot. The strip set `.,;:!?` is conservative — legitimate URLs don't end in these characters; if they do, percent-encoding survives the strip. |
| Test-only fix: reload BOTH `source_classes` AND `reddit` | `importlib.reload(sc)` resets REGISTRY but `sys.modules['source_classes.reddit']` is cached — the module body doesn't re-run, so the self-registration tail doesn't fire against the fresh list. Reloading both modules simulates a true cold start. This is the same constraint Plans 03 and 04 will hit in their own test files. |
| Chunk IDs grounded on `data.id`, not URL slug | Reddit slugs are derived from titles and can shift if a moderator edits the post; the `data.id` value is the stable Reddit-assigned identifier. Chunk-ID stability is load-bearing for re-ingest diffs. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Test `test_reddit_self_registers_into_registry` failed against a correct implementation**
- **Found during:** Task 1 first GREEN run
- **Issue:** The test reloaded `source_classes` (resetting `REGISTRY` to `[]`) and then did `from source_classes import reddit` — but `sys.modules['source_classes.reddit']` was cached from the earlier match_url tests, so reddit.py's module body never re-ran, the self-registration tail did not fire, and the assertion failed against an empty REGISTRY. The implementation was correct.
- **Fix:** Updated the test to also `importlib.reload(reddit_mod)` after reloading `source_classes`. Added a docstring inside the test explaining why both reloads are necessary (it mirrors how `__init__.py`'s `from . import reddit` line behaves on a cold start).
- **Files modified:** skills/patchbay-research/scripts/test_reddit.py
- **Verification:** All 12 tests pass; full research suite (24 tests including Plan 01's `test_core.py`) is 24/24 green.
- **Committed in:** ee6ce8f (folded into the Task 1 GREEN commit, since the test fix is part of landing GREEN).

**2. [Rule 2 — Missing Critical] Added idempotency guard to self-registration**
- **Found during:** While writing the test fix above, I noticed that re-running `reddit.py`'s module body via `importlib.reload` would append it a SECOND time to REGISTRY without a guard.
- **Issue:** A double-registered module would cause `route_url(url, REGISTRY)` to return the same module from both positions — a correctness violation if Plans 03/04 later add their own modules and ordering matters for the fallback. Not a bug today (reddit is the only entry), but a latent footgun.
- **Fix:** Wrapped the tail snippet in `_self = sys.modules[__name__]; if _self not in _REGISTRY: _REGISTRY.append(_self)`. Documented in the module docstring AND in this summary's `patterns-established` so Plans 03/04 inherit the same idempotency.
- **Files modified:** skills/patchbay-research/source_classes/reddit.py
- **Verification:** Repeated reload cycles in the test no longer cause duplicate appends; the membership check is O(1) on the small REGISTRY (max 4 entries).
- **Committed in:** ee6ce8f (folded into the Task 1 GREEN commit).

---

**Total deviations:** 2 auto-fixed (1 bug in test logic, 1 latent footgun in module-level pattern)
**Impact on plan:** Both fixes necessary for correctness. No scope creep — both changes live inside files the plan already listed in `<files>`. The patterns-established section now documents the idempotency guard so Plans 03/04 don't re-discover it.

## Issues Encountered

None beyond the two deviations above. No environment setup required — `urllib.parse`, `json`, `re`, `sys` are all stdlib. Plan 01 already installed `requests` and `pytest`.

## User Setup Required

None. Reddit's `.json` endpoint requires no auth, no API key, no extension.

## Interface Contract for Wave 2 / Wave 3 Plans

### For Plan 03 (Equipboard) and Plan 04 (YouTube):

1. Copy the **exact self-registration tail** from `reddit.py`:
   ```python
   from . import REGISTRY as _REGISTRY  # noqa: E402
   _self = sys.modules[__name__]
   if _self not in _REGISTRY:
       _REGISTRY.append(_self)
   ```
   The idempotency guard is REQUIRED — without it, `importlib.reload` in tests causes double-registration.

2. Append exactly ONE line to `source_classes/__init__.py`: `from . import equipboard` (or `youtube`, or `generic`). Read-modify-write only. The order between Plans 03 and 04 doesn't matter unless the generic fallback ships — `generic` MUST be the LAST append.

3. Mirror the **test harness pattern** in `test_reddit.py`:
   - Insert `_RESEARCH_ROOT = Path(__file__).resolve().parent.parent` into `sys.path` so `source_classes` resolves regardless of cwd.
   - Monkeypatch the aliased `_shared_fetch_tier1` via `unittest.mock.patch.object` for URL-rewrite verification.
   - Use a real-shaped fixture under `scripts/fixtures/<source>_sample.json` for `parse_to_chunks` tests.
   - The self-registration test reloads BOTH `source_classes` AND the source-class module.

4. Set `tier_used: 1` on every chunk. The acceptance contract is per-source.

### For Plan 05 (`--review-failures`):

Plan 02 does not interact with `failures.log` in the success path — Reddit's `.json` cheap path is universally reachable. On 404 (deleted thread) or 429 (rate limit), `classify_reason` in Plan 01's `log_failure.py` already classifies these as `("404", "skip")` and `("rate-limited", "skip")` respectively. Plan 05 should default the highlighted action for any Reddit failure to "skip" — there is no tier-2/3 path that adds information.

## Next Phase Readiness

- **Plan 03 (Equipboard) can start immediately.** The registry pattern is proven, the test harness is ready to copy, the read-modify-write append pattern is documented.
- **Plan 04 (YouTube) can start immediately.** Same scaffolding applies; YouTube's tier-1 path is the YouTube-Data-API-free yt-dlp + parse_vtt route documented in spike-findings.
- **No blockers.** No outstanding schema questions, no auth gates, no spike findings to chase.
- **One thing to watch in Plans 03/04:** the idempotency guard pattern from this plan is mandatory in every source-class module. Plan 02 documented it in the module docstring and in this summary's `patterns-established`; a copy-paste from `reddit.py` is the safest path.

## Self-Check: PASSED

Verification (all from the plan's `<verify>` lines + acceptance criteria):

- FOUND: skills/patchbay-research/source_classes/reddit.py
- FOUND: skills/patchbay-research/source_classes/__init__.py (modified, scaffold preserved)
- FOUND: skills/patchbay-research/references/source-class-reddit.md
- FOUND: skills/patchbay-research/scripts/test_reddit.py
- FOUND: skills/patchbay-research/scripts/fixtures/reddit_sample.json
- FOUND commits: fb47523 (Task 1 RED), ee6ce8f (Task 1 GREEN), b485af3 (Task 2 docs)
- pytest test_reddit.py: 12 passed, 0 failed
- pytest full research suite: 24 passed (12 core from Plan 01 + 12 reddit), 0 failed, no regressions
- grep `REGISTRY: list = []` in source_classes/__init__.py: present (Plan 01 scaffold preserved)
- grep `from . import reddit` in source_classes/__init__.py: present (Plan 02 single-line append landed)
- grep `reddit-<post_id>-c` in source-class-reddit.md: present
- grep `comment_aggregate` in source-class-reddit.md: present
- grep `external_resource` in source-class-reddit.md: present
- grep `review_section` in source-class-reddit.md: present
- grep `\.json` in source-class-reddit.md: present
- grep `## UI layer notes` in source-class-reddit.md: present (user memory rule satisfied)

---
*Phase: 03-patchbay-research-with-tiered-fetch*
*Completed: 2026-05-16*
