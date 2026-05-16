# failures.log Schema (locked — patchbay:research)

Canonical reference for the append-only JSONL `failures.log` written by `scripts/log_failure.py` during a `/patchbay:research` run. Every tier-1 fetch that does not produce a chunk produces exactly one line here. The user reviews this file via `/patchbay:research --review-failures` (Plan 05) and decides escalation per entry — **no automatic fallback** between tiers.

Origin: validated in spike 003 (see `.claude/skills/spike-findings-patchbay-plugin/references/web-scraping.md` § failures.log schema). Locked at Phase 3 plan kickoff.

## File location

`<gear_root>/<Brand Item>/knowledge/failures.log` — sits alongside `chunks.jsonl` in the per-gear knowledge store.

## Format

- **JSONL.** One JSON object per line, UTF-8 encoded, newline-terminated.
- **Append-only.** Writers never rewrite earlier lines; `--review-failures` resolves entries by appending new ones with an incremented `retry_count`, not by mutation.
- **Real JSON encoder.** Every line is the output of `json.dumps()` on a structured dict — never raw user input concatenated as a string. (T-03-03 mitigation.)

## Nine fields (all required, every line)

| Field | Type | Description |
|---|---|---|
| `timestamp` | string | ISO-8601 UTC, suffixed with `Z` (e.g., `2026-05-15T01:40:04Z`). Set on first write. |
| `url` | string | The URL as the user gave it. Do NOT over-canonicalize — different URL forms might fail differently and the citation-count layer dedupes downstream. |
| `tier_attempted` | int | Always `1` for entries written by `log_failure.log_failure`. Plan 05's escalation flow may write entries with `tier_attempted: 2` or `3` on re-attempts. |
| `http_status` | int | HTTP status code, or `0` if the request never reached a response (timeout, connection error). |
| `reason` | string | One of the eight values in § `reason` enum below. |
| `reason_detail` | string | Free-form. Includes the status code and a 200-character body snippet for inspection. On exceptions, includes the exception type and message. |
| `suggested_escalation` | int OR string | One of the five values in § `suggested_escalation` enum below. |
| `last_attempted` | string | ISO-8601 UTC, suffixed with `Z`. Equal to `timestamp` on first write; bumped on re-attempts by Plan 05. |
| `retry_count` | int | `1` on first write. Bumped by Plan 05's `--review-failures` flow when the user re-attempts a previously-failed URL. |

## `reason` enum (8 values)

| Value | Trigger | Suggested escalation |
|---|---|---|
| `cloudflare-block` | HTTP 403 AND body contains `"Just a moment..."` OR `"Checking your browser"` | `2` |
| `bot-detected` | HTTP 403 AND body contains `"captcha"` (case-insensitive) | `3` |
| `js-required` | HTTP 200 AND body contains `<noscript>` AND `len(body) < 5000` | `2` |
| `rate-limited` | HTTP 429 | `"skip"` |
| `paywall` | HTTP 402 OR body contains `"subscribe to read"` | `"manual-paste"` |
| `404` | HTTP 404 | `"skip"` |
| `timeout` | `requests.Timeout` raised | `"either"` |
| `other` | Any other non-2xx outcome | `"either"` |

## `suggested_escalation` enum (5 values)

Note the mixed types — integers and string literals coexist intentionally. The literal string `"either"` is distinct from numeric escalation tiers; consumers MUST handle both shapes.

| Value | Meaning |
|---|---|
| `2` | Escalate to tier 2 (real-browser fetch via `Claude_in_Chrome` MCP). Fast, DOM-aware, bypasses Cloudflare. |
| `3` | Escalate to tier 3 (computer-use + vision). Slower, viewport-only, bulletproof against any anti-bot. |
| `"either"` | String literal — both tier 2 and tier 3 are reasonable; user picks based on cost / site characteristics. |
| `"manual-paste"` | Demote to tier 0 — ask the user to paste the page's relevant DOM text by hand. The escape hatch for paywalled / account-gated content. |
| `"skip"` | No escalation worth attempting — the URL is dead (404), rate-limited (try later), or otherwise outside what `patchbay:research` can recover. |

## Example entry

```json
{
  "timestamp": "2026-05-15T01:40:04Z",
  "url": "https://equipboard.com/items/chase-bliss-audio-clean",
  "tier_attempted": 1,
  "http_status": 403,
  "reason": "cloudflare-block",
  "reason_detail": "Server returned 403. Body snippet: <!DOCTYPE html><html><head><title>Just a moment...</title>",
  "suggested_escalation": 2,
  "last_attempted": "2026-05-15T01:40:04Z",
  "retry_count": 1
}
```

## What `failures.log` is NOT

- **Not a chunk store.** Chunks go to `chunks.jsonl`. `failures.log` is metadata about URLs that DID NOT produce chunks.
- **Not a retry queue.** Plan 05's `--review-failures` is interactive — the user reviews and decides per entry. No background re-fetch.
- **Not over-canonicalized.** A trailing slash variant and a no-slash variant of the same URL are separate entries by design. Citation-count dedupe lives in Plan 04, not here.

## Origin

Synthesized from spike 003 (VALIDATED — `.claude/skills/spike-findings-patchbay-plugin/references/web-scraping.md`). Schema is locked at Phase 3 kickoff. Source-class plans (02 / 03 / 04) and the review-failures plan (05) consume this contract verbatim.
