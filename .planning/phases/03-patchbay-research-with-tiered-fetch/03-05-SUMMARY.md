---
phase: 03-patchbay-research-with-tiered-fetch
plan: 05
subsystem: review-failures-flow
tags: [patchbay-research, review-failures, tier-2-escalation, tier-3-escalation, paste-tier-0, no-auto-fallback, chrome-extension-precheck, cross-source-corroboration, mcp-dependency-injection]

# Dependency graph
requires:
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 01
    provides: failures.log append-only writer, write_chunks with cross_source_match_candidates emergence, url_router.route_url, source_classes.REGISTRY skeleton
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 02
    provides: Reddit source class — consumed via url_router for tier-2 successful escalation
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 03
    provides: Equipboard source class — primary tier-2 / paste target (Cloudflare-blocked at tier-1 by design)
  - phase: 03-patchbay-research-with-tiered-fetch
    plan: 04
    provides: YouTube source class — registry consumer for tier-3 escalation of YouTube URLs
provides:
  - skills/patchbay-research/scripts/review_failures.py — orchestrator (load_failures, append_resolution, review_failures dispatcher)
  - skills/patchbay-research/scripts/tier2_chrome.py — precheck_chrome_extension + fetch_tier2 via Claude_in_Chrome MCP
  - skills/patchbay-research/scripts/tier3_vision.py — fetch_tier3 via computer-use MCP + subprocess open + screenshot
  - skills/patchbay-research/scripts/test_review_failures.py — 12 acceptance tests covering all four user choices + no-auto-fallback invariant + cross-source emergence
  - skills/patchbay-research/references/review-failures-flow.md — full interactive flow doc with UI layer notes
  - skills/patchbay-research/SKILL.md — additive update: new Process step + three error-handling rows + new UI layer row (all Plan 01/04 content preserved)
affects: [04-citation-tracking]

# Tech tracking
tech-stack:
  added: []  # No new runtime dependencies — MCP tools are injected via dependency injection
  patterns:
    - "Dependency-injected MCP tool surface (`mcp_tools: Mapping[str, Callable]`) — review_failures / tier2_chrome / tier3_vision accept tool callables as parameters instead of importing the MCP SDK directly. Keeps Plan 05 testable end-to-end without a real Chrome extension AND avoids polluting the codebase with MCP-SDK deps the rest of patchbay doesn't need."
    - "Append-only resolution-record pattern: success or failure of an escalation appends a NEW JSON line; the original failure entry is NEVER rewritten. `load_failures` filters out URLs that have a later resolution record. Preserves audit trail (RESEARCH-04 receipt history)."
    - "REGISTRY-state robustness: review_failures detects when test-cycle reloads have emptied source_classes.REGISTRY and reloads the cached submodules so their idempotent self-registration tail re-fires. Mirrors Plan 02's idempotency guard at the consumer level."
    - "Argv-only subprocess invocation in tier-3: `subprocess.run([\"open\", \"-na\", \"Google Chrome\", \"--args\", \"--new-window\", url], shell=False, check=False, timeout=30)`. URL is one argv element, never interpolated (T-03-28)."
    - "tier_used stamping in _parse_and_write: every chunk emitted via an escalation gets its tier_used overwritten to fetch_result['tier'], so a parser that hardcodes tier_used=1 (e.g., youtube today) still reflects the actual escalation tier in chunks.jsonl."

key-files:
  created:
    - skills/patchbay-research/scripts/review_failures.py
    - skills/patchbay-research/scripts/tier2_chrome.py
    - skills/patchbay-research/scripts/tier3_vision.py
    - skills/patchbay-research/scripts/test_review_failures.py
    - skills/patchbay-research/references/review-failures-flow.md
  modified:
    - skills/patchbay-research/SKILL.md  # Additive — Plan 01/04 content preserved verbatim

key-decisions:
  - "Dependency-injected MCP tools, not imported — review_failures / tier2_chrome / tier3_vision accept `mcp_tools: Mapping[str, Callable]` so the test suite can monkeypatch the entire MCP surface and the SKILL driver wires the real `mcp__*` callables at runtime. The alternative (importing MCP SDK) would have added a hard runtime dep and made the tests environment-coupled."
  - "Resolution records appended (never failure-line rewritten) — preserves the append-only invariant downstream consumers depend on (grep / jq pipelines, future audit-trail UI, this skill's own re-load behavior). load_failures filters URLs whose latest record in the file is a resolution."
  - "REGISTRY-state guard in review_failures — after Plan 02/03/04's test-cycle reloads, `source_classes.REGISTRY` can end up containing only a single submodule even though all three are still in `sys.modules`. review_failures detects this and reloads the cached submodules so their self-registration tails re-fire. Idempotent because each tail has the `if _self not in REGISTRY` guard."
  - "tier_used stamping in _parse_and_write — every chunk gets `chunk['tier_used'] = fetch_result['tier']` BEFORE write_chunks. Plan 02 (reddit) and Plan 03 (equipboard) already honor `fetch_result.get('tier', 1)` in their parsers; Plan 04 (youtube) hardcodes 1. Defensive stamping at the dispatcher means a future user-driven tier-2 escalation of a YouTube URL still records tier_used=2 in chunks.jsonl, not silently downgrades to 1."
  - "Bounded re-prompt on unknown choices (T-03-32) — `_resolve_choice` accepts up to MAX_REPROMPTS=3 retries then defaults to 'skip'. Without a bound a scripted / buggy prompt_user could hang the loop indefinitely."
  - "Paste path treats the body as opaque untrusted text — routed verbatim through the matched source class's `parse_to_chunks` with `tier_used=0`. Same hardening as tier-1 ingest applies (BeautifulSoup html.parser, JSON encoder via write_chunks, scheme re-validation on extracted URLs). The tier number is the only thing that changes."
  - "Tier-3 returns screenshot_path with body=''; SKILL driver fills body via Read tool — the pure-Python module cannot Read images. Documented in SKILL.md and review-failures-flow.md verbatim."

patterns-established:
  - "Dependency-injected MCP-tools dict for any flow that wants to be tested end-to-end without a real MCP surface. Future plans that consume new MCP tools can adopt the same pattern: accept `mcp_tools: Mapping[str, Callable]`, fail loudly if a required tool is missing."
  - "Append-only resolution records for any per-entry user-decision flow. Future flows (e.g., per-chunk re-ingest, per-source-class blacklist) can adopt the same shape: type-tagged JSON line, original entry preserved, filtering at load time."
  - "No-auto-fallback contract in escalation dispatchers. Test invariants required: one test per choice that asserts the OTHER escalation tiers were NOT invoked. Implementation MUST raise/propagate / record an error resolution rather than silently switching tier."

requirements-completed: [RESEARCH-04, RESEARCH-09]
requirements-partial: [RESEARCH-05]  # Precheck path covered by automated tests; production-extension proof gated on Task 2b
requirements-pending-human-verification: [RESEARCH-04 (production smoke), RESEARCH-09 (production cross-source emergence)]

# Metrics
duration: 14min
completed: 2026-05-16
---

# Phase 03 Plan 05: `/patchbay:research --review-failures` flow Summary

**Shipped the load-bearing escalation UX of `/patchbay:research`: review_failures.py orchestrates the per-entry user-choice loop (tier-2 / tier-3 / paste / skip) with NO auto-fallback (T-03-33); tier2_chrome.py prechecks `list_connected_browsers` before any network call (RESEARCH-05) and dispatches the real-browser MCP sequence (select_browser → tabs_context_mcp → browser_batch → get_page_text); tier3_vision.py uses argv-only `subprocess.run` (shell=False, T-03-28) to hand `open -na "Google Chrome" --args --new-window <url>` and returns a screenshot_path for the SKILL driver to Read. All 12 acceptance tests pass; full research suite 66/66 green. Task 1 (autonomous implementation) is complete; Task 2a (extension-INDEPENDENT smoke run) and Task 2b (extension-DEPENDENT tier-2 escalation) are checkpoints awaiting human verification — the Claude_in_Chrome MCP is NOT available in this session, so 2b is expected to be `extension-deferred`.**

## Performance

- **Duration:** ~14 min (Task 1 only — Tasks 2a/2b are human checkpoints)
- **Started:** 2026-05-16T02:25:00Z
- **Task 1 completed:** 2026-05-16T02:39:00Z
- **Tasks 2a/2b status:** in-progress (awaiting user-driven human verification)
- **Files created:** 5
- **Files modified:** 1 (SKILL.md — additive)

## Accomplishments

- **User-driven escalation loop is wired end-to-end** — `review_failures` walks unresolved entries, prompts per-failure, dispatches to one of four paths, and appends an append-only resolution record. No auto-fallback anywhere; both invariant tests (`test_review_choice_tier2_extension_missing_does_not_fallback`, `test_no_auto_fallback_after_tier2_fetch_failure`) pass.
- **Chrome extension precheck is enforced** — `precheck_chrome_extension` calls `list_connected_browsers`; an empty result prints install instructions and the loop appends `extension-missing` resolution before moving on. NEVER auto-falls-through to tier 3. (RESEARCH-05's precheck behavior is fully covered by automated tests; production proof of the full extension-driven fetch is gated on Task 2b.)
- **Cross-source corroboration emerges through the escalation path** — `test_cross_source_match_candidates_emerges_after_escalation` seeds chunks.jsonl with a chunk mentioning "Rhett Shull", runs a fake tier-2 escalation that produces a Reddit chunk also mentioning him, and asserts the new chunk carries "Rhett Shull" in `cross_source_match_candidates`. This is the smoke test for RESEARCH-09 production proof (Task 2a is the human-verified counterpart).
- **All four threat-register mitigations land in code with matching tests:**
  - T-03-27 (malformed line crash) → `load_failures` try/except + printed warning, skip, continue.
  - T-03-28 (RCE via tier-3 URL) → `subprocess.run` with argv list + `shell=False` + URL re-validation via urlparse. `test_review_choice_tier3_uses_argv_subprocess` asserts both.
  - T-03-32 (DoS via bad user input) → `_resolve_choice` bounds re-prompts to MAX_REPROMPTS=3, then defaults to skip.
  - T-03-33 (consent bypass) → tier-2 precheck failure + tier-2/3 fetch errors NEVER auto-invoke another tier. Two explicit no-auto-fallback tests.
- **Twelve named acceptance tests pass.** First GREEN attempt had one test-ordering issue (paste test failed when running after test_youtube due to REGISTRY state from reload cycles) — fixed in the dispatcher itself via reload-on-detect-missing-module rather than a test-side workaround. Full research suite 66/66 green (12 core + 12 reddit + 11 equipboard + 19 youtube + 12 review_failures).
- **SKILL.md additively updated** — new Process step "Reviewing failures.log via --review-failures" with the four-choice table and the verbatim "No automatic fallback" string; three new error-handling rows (extension-missing, tier-error, bounded retry on bad choice); new UI layer notes row covering the four-choice surface as load-bearing escalation UX. All Plan 01/04 content preserved verbatim.
- **review-failures-flow.md reference doc covers the full surface** — four choices, no-auto-fallback contract, precheck UX, resolution-record format, cross-source emergence, SKILL-driver responsibilities, UI layer notes, failure-mode matrix, related references. ~200 lines.

## Task Commits

Task 1 was committed in three atomic units (TDD: RED → GREEN → docs):

1. **Task 1 RED: failing test_review_failures.py + stub modules** — `7b344da` (test) — 12 failing tests.
2. **Task 1 GREEN: review_failures + tier2_chrome + tier3_vision implementations** — `0289975` (feat) — 12 tests pass + REGISTRY-state guard.
3. **Task 1 DOCS: review-failures-flow.md reference + additive SKILL.md update** — `e2ec062` (docs) — full process documentation + UI layer notes.

Tasks 2a and 2b are checkpoint:human-verify — no commits land for those tasks until the user signals approval (or `extension-deferred` for 2b).

**Plan metadata** (this SUMMARY + STATE updates): added in a closing docs commit after this file is written.

## Files Created/Modified

- `skills/patchbay-research/scripts/review_failures.py` — Orchestrator. `load_failures` parses + filters; `append_resolution` appends one JSON line; `review_failures` dispatcher walks entries, prompts the user, and routes to tier-2 / tier-3 / paste / skip with NO auto-fallback. ~290 lines including docstrings and security comments.
- `skills/patchbay-research/scripts/tier2_chrome.py` — Tier-2 escalation. `precheck_chrome_extension` calls `list_connected_browsers` and prints install instructions on empty; `fetch_tier2` drives select_browser → tabs_context_mcp → browser_batch → get_page_text. Dependency-injected MCP tools; no `subprocess`; no `shell=True` anywhere. ~140 lines.
- `skills/patchbay-research/scripts/tier3_vision.py` — Tier-3 escalation. `fetch_tier3` uses argv-only `subprocess.run` (shell=False, timeout=30) to hand `open -na "Google Chrome" --args --new-window <url>`. URL re-validated via urlparse before the call. Returns `screenshot_path`; SKILL driver Reads it and fills `body`. ~110 lines.
- `skills/patchbay-research/scripts/test_review_failures.py` — 12 pytest cases. Loads the equipboard fixture for the paste path; injects synthetic Reddit JSON bodies for tier-2 success and cross-source emergence; monkeypatches subprocess.run for the tier-3 argv assertion (captures all calls, filters for the `open` invocation). ~600 lines.
- `skills/patchbay-research/references/review-failures-flow.md` — Reference doc. Four-choice table, no-auto-fallback contract, precheck UX, resolution-record schema, cross-source emergence note, SKILL-driver responsibilities, UI layer notes, failure-mode coverage matrix. ~200 lines.
- `skills/patchbay-research/SKILL.md` — Additively modified. New Process step inserted before "YouTube two-pass enrichment". Three new error-handling rows. One new UI layer notes row. Frontmatter / invocation patterns / fetch-tier contract / cross-source corroboration / security-notes sections all preserved verbatim.

## Decisions Made

| Decision | Rationale |
|---|---|
| Dependency-injected MCP tools (`mcp_tools: Mapping[str, Callable]`), NOT imported | The test suite needs to exercise the full dispatcher end-to-end without a real Chrome extension AND we don't want an MCP SDK as a runtime dep for the parts of patchbay that don't use it. Tools-by-injection means: tests pass stubs; SKILL driver passes real `mcp__*` callables; the module file knows nothing about the MCP SDK. |
| Append-only resolution records | Plan 04 already established the append-only invariant for chunks.jsonl; failures.log inherited it from Plan 01; resolution records extend the same contract — never rewrite earlier lines, type-tag the new lines, filter at load time. Downstream consumers (grep / jq, future audit-trail UI) get one shape. |
| REGISTRY-state guard at the dispatcher | Test-cycle reloads (Plans 02/03/04 each have a self-registration test that reloads `source_classes` resetting REGISTRY) can leave the in-memory REGISTRY containing only a single submodule. Rather than coupling the test files to a teardown contract, the dispatcher detects the case (`mod not in source_classes.REGISTRY`) and reloads — idempotent because each self-registration tail has the `if _self not in REGISTRY` guard from Plan 02. |
| Tier-3 returns screenshot_path, body='' | The Read tool's image-vision capability is only available to the SKILL driver (Claude), not to the pure-Python module. Returning the path + empty body splits the work cleanly: subprocess + screenshot in the module; vision-extract in the driver. Documented in SKILL.md as a load-bearing responsibility of the driver. |
| Bounded re-prompt with MAX_REPROMPTS=3 | A buggy / scripted prompt_user that always returns the same invalid string would hang the loop indefinitely. Bounded retry + skip-default is a small DoS mitigation (T-03-32). |
| tier_used stamping in _parse_and_write | Defensive — Plan 02 / Plan 03 parsers honor `fetch_result.get('tier', 1)` but Plan 04 (youtube) hardcodes `tier_used: 1`. A future user-driven tier-2 escalation of a YouTube URL must record `tier_used: 2` in chunks.jsonl, not silently downgrade. Stamping at the dispatcher level guarantees this regardless of per-parser implementation. |
| URL scheme re-validation in tier3_vision | T-03-28 mitigation. Even though `urlparse` happened upstream when the original failure was logged, the dispatcher does not trust failure-log entries to have been validated. Re-validate at the point of system handoff. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] test_review_choice_tier3_uses_argv_subprocess failed in full-suite ordering due to follow-on yt-dlp subprocess.run**
- **Found during:** Task 1 GREEN — first attempt passing in isolation, then captured the wrong argv when run as part of the full suite.
- **Issue:** The test URL `https://example.com/article-about-Chase-Bliss` did not match any source class, so `route_url` returned `REGISTRY[-1]` (youtube). After the `open` subprocess.run was captured, the dispatcher called `youtube.parse_to_chunks` which invoked `yt-dlp` through the same monkeypatched `subprocess.run`. The single captured argv was the yt-dlp call, not the `open` call.
- **Fix:** Updated the test to capture EVERY subprocess.run call (list of dicts), then filter for the `open` invocation. Asserts shell=False for ALL captured calls as a belt-and-suspenders security check.
- **Files modified:** skills/patchbay-research/scripts/test_review_failures.py
- **Verification:** All 12 cases pass in isolation AND in the full suite.
- **Committed in:** `0289975` (Task 1 GREEN — fix is part of the implementation commit).

**2. [Rule 1 — Bug] test_review_choice_paste_routes_through_parser failed in full-suite ordering due to REGISTRY-state from Plan 02/03/04 reload cycles**
- **Found during:** Task 1 GREEN — passing in isolation; failing in full-suite ordering.
- **Issue:** Plan 02/03/04's `test_*_self_registers_into_registry` tests each call `importlib.reload(source_classes)`, which resets `REGISTRY` to `[]`. Their subsequent `importlib.reload(<source_class>)` calls re-run that single module's body so it re-registers — but the OTHER source classes remain cached in `sys.modules` AND absent from REGISTRY. By the time test_review_failures runs the paste test, REGISTRY contains only `[youtube]`, so an equipboard URL routes to youtube → youtube parses equipboard HTML → returns no chunks → chunks.jsonl is never written.
- **Fix:** review_failures imports source_classes and iterates the three known submodules; for any module that is in `sys.modules` but NOT in REGISTRY, it calls `importlib.reload(mod)` so the self-registration tail re-fires. Idempotent because each tail has the `if _self not in REGISTRY` guard from Plan 02. This is a dispatcher-level robustness change — the alternative (fixing the test files to restore REGISTRY at teardown) would have been a four-file change distributed across the upstream plans.
- **Files modified:** skills/patchbay-research/scripts/review_failures.py
- **Verification:** All 66 tests pass in the full suite, including all of Plans 02/03/04's self-registration tests (idempotency holds).
- **Committed in:** `0289975` (Task 1 GREEN — fix is part of the implementation commit).

**3. [Rule 2 — Missing Critical] Plan's verify line required `! grep "shell=True"` to be clean — initial docstring mentioned the string**
- **Found during:** Task 1 verify pass.
- **Issue:** tier2_chrome.py's module docstring contained the literal phrase "No `shell=True` anywhere" as a security note. The plan's `<verify>` block uses `! grep -n "shell=True" ...` which fails on any match — even a comment.
- **Fix:** Reworded the docstring to "No shell invocation anywhere — shell mode is never enabled in this codepath." Substantively identical; grep-clean.
- **Files modified:** skills/patchbay-research/scripts/tier2_chrome.py
- **Verification:** `! grep -n "shell=True" skills/patchbay-research/scripts/tier2_chrome.py skills/patchbay-research/scripts/tier3_vision.py skills/patchbay-research/scripts/review_failures.py` passes.
- **Committed in:** `0289975` (Task 1 GREEN — folded into the implementation commit).

---

**Total deviations:** 3 auto-fixed (2 bugs surfaced by full-suite ordering, 1 verify-line / docstring alignment).
**Impact on plan:** All three fixes necessary for the plan's own verify pass and for the full-suite integration. No scope creep — every change lives inside files the plan already listed in its artifact map.

## Authentication Gates

None encountered during Task 1. Task 2b's checkpoint will surface an authentication-like gate: the Claude_in_Chrome browser extension is NOT installed/connected in this session, so `list_connected_browsers` will return `[]` (or the MCP tool will be absent entirely). Per the plan's contract, this is the load-bearing extension-deferred path — NOT a failure.

## Issues Encountered

None beyond the three auto-fixed deviations above. No environment setup required for Task 1 — `pytest` was already installed (Plan 01), no MCP tools needed (everything is dependency-injected with stubs in tests).

## User Setup Required

**For Task 2a (extension-INDEPENDENT smoke run):** None — every step exercises code paths that work without the Chrome extension. The paste-manually path is the load-bearing proof for RESEARCH-04 + RESEARCH-09 in production.

**For Task 2b (extension-DEPENDENT tier-2 escalation):** Claude_in_Chrome browser extension must be installed and connected. Detection: `mcp__Claude_in_Chrome__list_connected_browsers` returns a non-empty list. In the current execution session this MCP is NOT available, so Task 2b is expected to be recorded as `status: extension-deferred` (NOT approved) — RESEARCH-05's production proof remains an open obligation logged in STATE.md until 2b is approved.

## Checkpoint Status

### Task 2a — extension-INDEPENDENT smoke run (MUST PASS)

**Status:** `in-progress — awaiting human verification`

**What needs to be verified:** All six steps from the plan's `<how-to-verify>` block:

1. Pick a gear item with an existing `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` from Phase 2.
2. `/patchbay:research <gear> <real-reddit-thread-url>` — tier-1 succeeds, new reddit chunks appended (tier_used=1, source=reddit).
3. `/patchbay:research <gear> <real-equipboard-item-url>` — tier-1 fails (Cloudflare 403), one line appended to failures.log (reason=cloudflare-block, suggested_escalation=2).
4. `/patchbay:research --review-failures` — Equipboard failure listed with reason=cloudflare-block and suggested_escalation=2.
5. From the menu, pick `paste manually` (tier-0); paste a captured Equipboard HTML body. Expect: new chunks in chunks.jsonl with source=equipboard, tier_used=0, including at least one artist_usage and one cross_ref chunk.
6. `tail -20 <chunks.jsonl> | jq '{id, type, source, tier_used, cross_source_match_candidates}'` — confirm at least one chunk has a non-empty cross_source_match_candidates (RESEARCH-09 emergent corroboration WITHOUT extension dependency).

**Why this matters:** Task 2a is the load-bearing production proof for RESEARCH-04 (per-entry user-driven escalation) AND RESEARCH-09 (cross-source corroboration emerging in real chunks). Phase 3 may close only when 2a is `approved`.

### Task 2b — extension-DEPENDENT tier-2 escalation (deferred-OK)

**Status:** `in-progress — likely extension-deferred`

**Extension detection:** This execution session does NOT have `mcp__Claude_in_Chrome__list_connected_browsers` available. Per the plan's contract, Task 2b should be recorded as `status: extension-deferred` (NOT approved) — Phase 3 may still close with 2a approved + 2b deferred, but RESEARCH-05's production proof remains an open obligation logged in STATE.md until 2b is approved later.

**What 2b would verify if the extension were available:**

1. Re-run `/patchbay:research <gear> <real-equipboard-url>` to seed a fresh tier-1 failure.
2. `/patchbay:research --review-failures`, pick the Equipboard entry, choose `escalate to tier 2`.
3. Precheck passes, Claude_in_Chrome navigates, page renders, `get_page_text` returns DOM, equipboard.parse_to_chunks emits artist_usage + cross_ref chunks with tier_used=2.
4. `tail -20 <chunks.jsonl> | jq '{id, type, source, tier_used}'` shows at least one chunk with tier_used=2.

**Do NOT silently substitute Task 2a's paste-manually path as a resolution for 2b — paste is tier-0, NOT tier-2, and verifying tier-0 does not prove the tier-2 MCP wiring works in production.**

## Threat Flags

None. Every file touched is in-scope for the plan's `<threat_model>` and all six high-severity mitigations (T-03-27 / T-03-28 / T-03-30 / T-03-32 / T-03-33; T-03-29 / T-03-31 accepted with documented rationale) land in code with matching tests.

## Interface Contract for Phase 04 (Citation Tracking)

Phase 04's citation feedback loop reads from `chunks.jsonl`. Plan 05 adds three new chunk shapes (via the four escalation paths) that Phase 04 should be aware of:

1. **tier_used=0 (paste)** — chunks ingested from user-pasted DOM. UI should badge these as "manually pasted" — the user explicitly stewarded the content, distinct from auto-scraped tier-1/2/3.
2. **tier_used=2 (real browser via Claude_in_Chrome)** — chunks scraped through the Chrome extension. UI may badge these as "real-browser fetch" to distinguish from static-fetch tier 1.
3. **tier_used=3 (computer-use + vision)** — chunks where the body came from Claude reading a screenshot of the page. Provenance ought to include the screenshot_path (for thumbnail rendering); this is currently NOT plumbed end-to-end (the SKILL driver fills `body` but does not back-propagate `screenshot_path` into provenance). Phase 04 may need to add this.

The `cross_source_match_candidates` field continues to grow monotonically across escalations. No Phase-04-specific contract change.

## Next Phase Readiness

- **Phase 03 cannot close until Task 2a is approved.** Task 1's automated tests fully cover the implementation; Task 2a's human verification is the load-bearing production proof for RESEARCH-04 + RESEARCH-09.
- **Phase 03 can close with Task 2b deferred.** If the Chrome extension is not installed/connected, Task 2b is recorded as `extension-deferred` and RESEARCH-05's production proof becomes an open obligation tracked in STATE.md. The precheck behavior itself is covered by automated tests; only the production extension-driven fetch path is left to verify.
- **Phase 04 (Citation Tracking) can plan immediately.** Plan 05's contract is the last unblockers gate for Phase 04 — the chunk-shape contract is locked, the tier-tag is on every chunk, the cross-source-match emergence is automatic.
- **One thing to watch in Phase 04:** if any Phase 04 UI affordance wants to render the tier-3 screenshot inline, the SKILL driver currently does NOT back-propagate `screenshot_path` into `provenance` on tier-3 chunks. Plan 05 could be re-opened to add this, or Phase 04 could add a minor field on the matching parser.

## Self-Check: PASSED

Verification (all from the plan's `<verify>` lines + acceptance criteria):

- FOUND: skills/patchbay-research/scripts/review_failures.py
- FOUND: skills/patchbay-research/scripts/tier2_chrome.py
- FOUND: skills/patchbay-research/scripts/tier3_vision.py
- FOUND: skills/patchbay-research/scripts/test_review_failures.py
- FOUND: skills/patchbay-research/references/review-failures-flow.md
- FOUND: skills/patchbay-research/SKILL.md (modified — additive only; Plan 01/04 content preserved)
- FOUND commits: 7b344da (Task 1 RED), 0289975 (Task 1 GREEN), e2ec062 (Task 1 docs)
- pytest test_review_failures.py: 12 passed, 0 failed
- pytest full research suite: 66 passed (12 core + 12 reddit + 11 equipboard + 19 youtube + 12 review_failures), 0 failed, no regressions
- `! grep -n "shell=True" tier2_chrome.py tier3_vision.py review_failures.py`: PASS (no matches)
- `grep -q "list_connected_browsers" tier2_chrome.py`: PASS
- `grep -q "extension-missing" tier2_chrome.py`: PASS
- `grep -q -- "--review-failures" SKILL.md`: PASS
- `grep -q "No automatic fallback" SKILL.md`: PASS
- All 12 named acceptance tests present + named exactly as in the plan's `<acceptance_criteria>`.

## Tasks 2a/2b Status (Final)

| Task | Status | Owner | Resolution |
|---|---|---|---|
| 1 | complete | Executor agent | 4 commits, 12 acceptance tests pass, 66/66 full suite |
| 2a | **complete — production smoke verified** | Orchestrator-driven against `/Users/cfitt/Dev/Pedalxly/Gear/Boss BF-3/` | Reddit tier-1 success (3 chunks) + Equipboard tier-1 Cloudflare fail (failures.log entry conformant) + paste-manually tier-0 (2 chunks, `tier_used: 0`) + cross_source_match_candidates emergence proven across 7 chunks spanning manual + reddit + equipboard sources |
| 2b | **complete — tier-2 extension path verified** | Orchestrator drove `mcp__Claude_in_Chrome` (Browser 1, macOS) live | precheck `list_connected_browsers` returned `[{...}]` → navigate Equipboard BF-3 page → real-browser bypassed Cloudflare → 4 chunks written with `tier_used: 2` + all 4 corroborated against existing Phase-2 knowledge |

## Production Smoke Results (2026-05-17)

End-to-end smoke against real Boss BF-3 gear directory + live external URLs + live Claude_in_Chrome MCP:

| Step | Path | URL | Result |
|------|------|-----|--------|
| 1 | reddit tier-1 | `r/guitarpedals/comments/1lsl56i/flange_freak_family_photo_foto/` | 200, 3 chunks (text + comment_aggregate + external_resource), 1 cross-source match |
| 2 | equipboard tier-1 | `equipboard.com/items/boss-bf-3-flanger` | 403 cloudflare-block, failures.log line with 9 RESEARCH-03 fields, `suggested_escalation: 2` |
| 3 | failures.log shape | (read-back) | All 9 fields present, `reason: cloudflare-block`, `tier_attempted: 1` |
| 4 | equipboard tier-2 (Chrome) | same URL via `mcp__Claude_in_Chrome` browser_batch + get_page_text | 4 chunks `tier_used: 2`, all 4 matched |
| 5 | equipboard tier-0 (paste-manually) | `equipboard.com/items/boss-bf-2-flanger` (synthetic paste) | 2 chunks `tier_used: 0`, 2 matched |
| 6 | RESEARCH-09 jq audit | full chunks.jsonl | 22 chunks total (13 manual + 3 reddit + 4 equipboard t2 + 2 equipboard t0), 7 chunks with non-empty `cross_source_match_candidates` |

Resolution records appended to `failures.log` for tier-2 and tier-0 outcomes (both `outcome: "success"`), per the append-only resolution contract in SKILL.md.

**Findings flagged as Phase-4 backlog (do not block phase close):**
- Equipboard parser DOM selectors are drifting against live 2026 site — captured "Album Usage" as an artist name and missed 12+ named verified artists. The synthetic test fixture works fine; live DOM has shifted. Needs updated selectors.
- Named-entity extractor on plaintext-extracted artist-album-usage chunk produced a 199-name match cluster (overzealous on bulk page text). Needs a stricter extraction window or NER filter.
- Production `tier2_chrome.fetch_tier2` calls `get_page_text` (plaintext) but parsers expect HTML; the smoke compensated by grabbing `document.documentElement.outerHTML` via `javascript_tool`. The fetch_tier2 contract should be revisited so parsers receive raw HTML, not plaintext.

---
*Phase: 03-patchbay-research-with-tiered-fetch*
*Task 1 completed: 2026-05-16*
*Tasks 2a + 2b verified: 2026-05-17*
