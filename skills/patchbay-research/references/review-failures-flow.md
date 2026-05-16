# `/patchbay:research --review-failures` — interactive flow

This reference documents the user-driven escalation loop that wraps the
cheap-by-default tier-1 spine of `/patchbay:research`. It is the load-bearing
UX of **RESEARCH-04** (per-entry user choice) and **RESEARCH-05** (Chrome
extension precheck before any tier-2 work).

For the cross-source corroboration that emerges automatically from successful
escalations, see [`SKILL.md` § Cross-source corroboration](../SKILL.md) and
the test
[`test_cross_source_match_candidates_emerges_after_escalation`](../scripts/test_review_failures.py)
which verifies **RESEARCH-09** against a real `write_chunks` round-trip.

---

## What `--review-failures` is for

After a tier-1 research run, each URL that failed (Cloudflare block, paywall,
404, etc.) is appended as a single JSON line to
`<gear_root>/<Brand Item>/knowledge/failures.log`. **No automatic escalation
to tier 2 or 3 ever runs.** The user decides what to escalate, per entry, via
this flow.

```bash
/patchbay:research --review-failures
```

The skill walks each unresolved failure (a failure whose URL has no later
resolution record in the same file) and prompts for one of four choices.

---

## The four choices (locked, per RESEARCH-04)

| Choice               | What it does                                                                 | Implemented by                      |
|----------------------|------------------------------------------------------------------------------|-------------------------------------|
| `escalate to tier 2` | Real-browser fetch via the **Claude in Chrome** MCP extension                | `tier2_chrome.fetch_tier2`          |
| `escalate to tier 3` | System-level Chrome handoff + viewport screenshot + Claude vision           | `tier3_vision.fetch_tier3`          |
| `paste manually`     | Tier 0 — user pastes DOM text; we route it through the matched source class | `review_failures._parse_and_write`  |
| `skip`               | Record a `user-skipped` resolution; never retry                              | `review_failures.append_resolution` |

Any other input re-prompts up to 3 times, then defaults to `skip` (T-03-32 —
bounded retry so a buggy/scripted `prompt_user` cannot hang the loop).

---

## NO automatic fallback (T-03-33)

This is the consent-bypass invariant that makes the cheap-by-default model
honest. Specifically:

1. If the user picks `tier-2` and the precheck fails (extension not connected),
   the loop appends a `extension-missing` resolution and **moves on**. It does
   NOT silently try tier 3.
2. If the user picks `tier-2` and the fetch raises an exception (network error,
   MCP misbehavior, etc.), the loop appends a `tier-error` resolution and
   **moves on**. It does NOT silently try tier 3.
3. If the user picks `tier-3` and that fetch raises, same story — `tier-error`
   resolution, move on.

Covered by `test_review_choice_tier2_extension_missing_does_not_fallback` and
`test_no_auto_fallback_after_tier2_fetch_failure`.

---

## Per-entry prompts

For each failure, the user sees a one-line summary:

```
[review_failures] https://equipboard.com/items/chase-bliss-clean  reason='cloudflare-block'  http_status=403  suggested_escalation=2
```

…then the action prompt (which the CLI / UI wires to `prompt_user`):

```
> escalate to tier 2 / escalate to tier 3 / paste manually / skip
```

Recognized inputs (case-insensitive, whitespace-trimmed):
`tier-2`, `tier-3`, `paste`, `skip`.

For the `paste` path, the user is then prompted a second time with the URL
they're pasting for:

```
Paste the DOM text for https://equipboard.com/items/chase-bliss-clean (end with EOF / Ctrl-D):
```

The pasted body is treated as opaque untrusted text (T-03-30) and routed
through the matched source class's `parse_to_chunks` — same hardening as
tier-1 ingest (BeautifulSoup `html.parser`, JSON encoding via `write_chunks`,
URL scheme re-validation on extracted external links). The only thing that
changes is `tier_used: 0` on every emitted chunk.

---

## The Chrome extension precheck (RESEARCH-05)

Before any tier-2 fetch ever happens:

```python
mcp_tools["list_connected_browsers"]()
```

If the result is empty or the MCP tool is unavailable in the current session,
`precheck_chrome_extension` prints:

```
Claude in Chrome extension is not connected. Install from
https://chrome.google.com/webstore/detail/claude-in-chrome/<extension-id>
and reload the page. Then re-run `/patchbay:research --review-failures` and
choose `escalate to tier 2` again. (No automatic fallback to tier 3 — the
user retains agency.)
```

…appends a resolution with `outcome: "extension-missing"`, and continues to
the next failure. The user can either install the extension or pick a
different choice next time.

`list_connected_browsers` returning a non-empty list (e.g.,
`[{"deviceId": "abc"}]`) is taken at face value — the MCP tool surface is
trusted infrastructure per T-03-29.

---

## Resolution-record format (append-only)

After every action, one JSON line is appended to `failures.log`:

```json
{"type": "resolution", "url": "https://equipboard.com/items/chase-bliss-clean",
 "resolved_at": "2026-05-16T10:11:12Z", "tier_used": 2, "outcome": "success",
 "chunks_written": 7}
```

| Field            | Type             | Notes                                                            |
|------------------|------------------|------------------------------------------------------------------|
| `type`           | `"resolution"`   | Sentinel — distinguishes resolution records from failure entries |
| `url`            | string           | Matches the URL of the failure being resolved                    |
| `resolved_at`    | ISO 8601 Z       | UTC                                                              |
| `tier_used`      | `0` / `2` / `3` / `null` | `null` only for `user-skipped`                            |
| `outcome`        | enum             | `success`, `user-skipped`, `extension-missing`, `tier-error`     |
| `chunks_written` | int              | `0` for non-success outcomes                                     |

The original failure line is **never rewritten**. This preserves the
append-only invariant that downstream consumers (a future "audit trail UI",
grep / jq pipelines, this skill's own re-load on a subsequent run) depend on.

---

## Cross-source corroboration (RESEARCH-09)

Successful escalations write their chunks via the same `write_chunks` helper
used by tier-1, so `cross_source_match_candidates` is populated automatically
against everything already in `chunks.jsonl` — including chunks from prior
runs of `patchbay:ingest` (manual ingest) and prior `--review-failures`
escalations.

A worked smoke-test of this property lives in
`test_cross_source_match_candidates_emerges_after_escalation` — pre-seed
`chunks.jsonl` with a chunk mentioning "Rhett Shull", run a fake tier-2
escalation that produces a Reddit chunk also mentioning him, assert the new
chunk carries `"Rhett Shull"` in `cross_source_match_candidates`.

No separate ranking pass. No re-scan of older chunks. The field grows
monotonically.

---

## SKILL driver responsibilities

When the SKILL.md driver wires `prompt_user` and `mcp_tools` for real
production runs:

| Hook                          | What the driver provides                                                                |
|-------------------------------|-----------------------------------------------------------------------------------------|
| `prompt_user(entry)`          | Show the per-entry summary + ask one of the four choices                                |
| `prompt_user(<paste prompt>)` | Capture multi-line user paste up to EOF / Ctrl-D                                        |
| `mcp_tools["list_connected_browsers"]` | The real `mcp__Claude_in_Chrome__list_connected_browsers`                       |
| `mcp_tools["select_browser"]`        | The real `mcp__Claude_in_Chrome__select_browser`                                  |
| `mcp_tools["tabs_context_mcp"]`      | The real `mcp__Claude_in_Chrome__tabs_context_mcp`                                |
| `mcp_tools["browser_batch"]`         | The real `mcp__Claude_in_Chrome__browser_batch`                                   |
| `mcp_tools["get_page_text"]`         | The real `mcp__Claude_in_Chrome__get_page_text`                                   |
| `mcp_tools["request_access"]`        | The real `mcp__computer-use__request_access`                                      |
| `mcp_tools["screenshot"]`            | The real `mcp__computer-use__screenshot`                                          |

The tier-3 path returns a `screenshot_path`; the SKILL driver **Reads** that
path (the Read tool's vision affordance), produces the body text, and
substitutes `body` in the `fetch_result` dict before passing to
`parse_to_chunks`. The pure-Python entry point cannot Read images.

---

## UI layer notes

(Per the project rule: parallel UI notes required in every patchbay spec.)

| Decision                                                        | UI implication                                                                                 |
|-----------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| `failures.log` resolution records are append-only JSON lines    | UI renders a "review failures" surface directly from this file — same shape as the CLI flow    |
| Four choices, locked, never auto-fallback                       | UI shows four buttons per failure; never a "try all" / "auto-escalate" affordance              |
| `tier_used` populated on every chunk (`0` / `2` / `3`)          | UI badges trust profile: paste, real-browser, vision                                           |
| Pre-`tier-2` precheck gates the tier-2 button on extension status | UI greys out "tier 2" when `list_connected_browsers` is empty; install link surfaced inline   |
| Pasted body parser is the same as tier-1                        | UI's "paste body" textarea has no source-class selector — the matched class is implied by URL  |

---

## Failure-mode coverage at a glance

| Situation                                          | Outcome recorded         | Counts incremented |
|----------------------------------------------------|--------------------------|--------------------|
| User picks tier-2, precheck `[]`                   | `extension-missing`      | `extension_missing` + `processed` |
| User picks tier-2, precheck OK, fetch succeeds     | `success`                | `escalated` + `processed`         |
| User picks tier-2, precheck OK, fetch raises       | `tier-error`             | `processed` (no escalated bump)   |
| User picks tier-3, fetch succeeds                  | `success`                | `escalated` + `processed`         |
| User picks tier-3, fetch raises                    | `tier-error`             | `processed`                       |
| User picks paste, parse succeeds                   | `success`                | `escalated` + `processed`         |
| User picks paste, parse raises                     | `tier-error`             | `processed`                       |
| User picks skip                                    | `user-skipped`           | `skipped` + `processed`           |
| User input invalid 4 times in a row                | (defaults to skip → `user-skipped`) | `skipped` + `processed` |

---

## Related references

- [`failures-log-schema.md`](failures-log-schema.md) — the nine-field schema this flow consumes.
- [`source-class-registry.md`](source-class-registry.md) — the three-callable contract every source class exposes.
- [`source-class-reddit.md`](source-class-reddit.md), [`source-class-equipboard.md`](source-class-equipboard.md), [`source-class-youtube.md`](source-class-youtube.md) — per-source parser docs.
- [`SKILL.md`](../SKILL.md) — the skill entry point; the `--review-failures` invocation pattern dispatches into this flow.
- [`scripts/test_review_failures.py`](../scripts/test_review_failures.py) — the 12-case acceptance contract for the flow.
