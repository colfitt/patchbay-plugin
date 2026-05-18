---
name: patchbay-research
description: Research a piece of gear by ingesting web sources (Equipboard, Reddit, articles, YouTube) into the per-gear knowledge store via a tiered fetch ladder. Activates on "/patchbay:research [gear]", "/patchbay:research [gear] [url]", "/patchbay:research --review-failures", "research [gear] online", and "find reviews for [gear]". Tier-1 static fetch tries first; on failure, a structured entry is appended to failures.log for user-driven escalation. No auto-fallback.
---

# patchbay:research

Pull web-source knowledge into a gear's `chunks.jsonl` — Equipboard artist-usage edges, Reddit long-form reviews, articles, YouTube multimodal segments. Every chunk lands in the same per-gear knowledge store that `patchbay:ingest` writes manual chunks to, with full provenance for the future citation-hover UX. The fetch ladder is cheap-by-default + user-driven escalation: tier-1 tries first, failures get logged, **you** decide what to escalate.

**Before starting any research run**, read these reference files:
- `references/convention.md` (plugin root) — gear folder layout, `gear_root` resolution from `patchbay.yml`
- `references/inventory.md` (plugin root) — owned-gear normalization, how to resolve a `<gear>` arg against `<Brand Item>` folders
- `skills/patchbay-research/references/failures-log-schema.md` — the locked 9-field failures.log schema (this file consumes it)
- `skills/patchbay-research/references/source-class-registry.md` — the three-callable contract (`match_url`, `fetch_tier1`, `parse_to_chunks`) every source-class module exposes
- `skills/patchbay-ingest/references/chunk-schema.md` — every chunk this skill writes MUST conform to the required-field set (`id`, `type`, `source`, `content`, `provenance` with `scraped_at`)
- `skills/patchbay-research/references/citations-flow.md` — the `--citations` subcommand (Plan 04-02 output, consumed by Plan 04-03)

## Invocation patterns

Activate on any of these patterns:

```
"/patchbay:research [gear]"            → gather candidate URLs for the gear, route + fetch each at tier 1
"/patchbay:research [gear] [url]"      → single-URL research path; bypass discovery
"/patchbay:research --review-failures" → load failures.log, walk the user through per-entry escalation
"/patchbay:research --citations [gear]"   → list external resources cited by >= N independent sources (default N=2)
"research [gear] online"               → same as bare /patchbay:research [gear]
"find reviews for [gear]"              → same as bare /patchbay:research [gear]
```

The `--review-failures` flow lives in **Plan 05**'s deliverable but is dispatched from this SKILL.md — the entry point is here so the same skill activates whether the user is starting a fresh research run or returning to triage prior failures.

## The fetch-tier contract

Tier-1 static fetch is attempted first for every URL. On HTTP non-2xx or detected anti-bot challenge, a JSON line is appended to `<gear_root>/<Brand Item>/knowledge/failures.log`. **No automatic fallback to tier 2 or tier 3.** The user reviews failures via `/patchbay:research --review-failures` and chooses escalation per entry.

### `reason` enum (8 values — surface inline)

| Value | Trigger | Suggested escalation |
|---|---|---|
| `cloudflare-block` | 403 + body contains `"Just a moment..."` or `"Checking your browser"` | `2` |
| `bot-detected` | 403 + body contains `"captcha"` (case-insensitive) | `3` |
| `js-required` | 200 + `<noscript>` + body < 5000 chars | `2` |
| `rate-limited` | 429 | `"skip"` |
| `paywall` | 402 or `"subscribe to read"` in body | `"manual-paste"` |
| `404` | 404 | `"skip"` |
| `timeout` | `requests.Timeout` raised | `"either"` |
| `other` | Any other non-2xx | `"either"` |

### `suggested_escalation` enum (5 values — note the mixed types, including literal `"either"`)

| Value | Meaning |
|---|---|
| `2` | Tier 2 — real-browser fetch via `Claude_in_Chrome` MCP. DOM-aware, bypasses Cloudflare. |
| `3` | Tier 3 — computer-use + vision. Slower, viewport-only, bulletproof against any anti-bot. |
| `"either"` | Both are reasonable; user picks based on cost vs. site characteristics. |
| `"manual-paste"` | Tier 0 — ask the user to paste relevant DOM text. Escape hatch for paywalls. |
| `"skip"` | No escalation worth attempting. URL is dead or out-of-scope. |

Full schema with examples: [`references/failures-log-schema.md`](references/failures-log-schema.md).

## Process

### Step 1: Resolve gear → knowledge dir

1. Parse the `<gear>` arg (or prompt if missing). Normalize via `references/inventory.md` rules (case-insensitive brand+name matching, three-level fallback if needed).
2. Resolve `gear_root` from `patchbay.yml` (default `Gear/`).
3. Target folder: `<gear_root>/<Brand Item>/`. If the folder does not exist, stop:

   > "No gear folder found for [gear]. Run `patchbay:add-gear` first, or check that your folder name matches `<Brand> <Item>` (e.g., `Chase Bliss MOOD MkII`)."

4. Knowledge dir: `<gear_root>/<Brand Item>/knowledge/`. If absent, create it. `chunks.jsonl` and `failures.log` both land here.

### Step 2: Gather candidate URLs

If the user supplied a URL on the command line (`/patchbay:research <gear> <url>`), use that. Otherwise, build a candidate list:

- The gear's Equipboard page (if known — discoverable via a search query the user confirms).
- Reddit threads found via search (e.g., site:reddit.com `<gear>` review).
- Manufacturer page (if available).
- Top-voted YouTube reviews for the gear.

Present the list to the user; let them prune. The skill works on the approved list, one URL at a time — no parallel fetches.

Record `scraped_at` ONCE at this point as an ISO 8601 timestamp; every chunk produced in this run carries the same value.

### Step 3: Route each URL via `url_router.route_url`

For every URL in the approved list, dispatch to its source-class module:

```python
from skills.patchbay_research.source_classes import REGISTRY
from skills.patchbay_research.scripts.url_router import route_url

source_class = route_url(url, REGISTRY)
```

The router walks `REGISTRY` and returns the first module whose `match_url(url)` returns True. Unknown hosts fall through to the **generic** source class (`REGISTRY[-1]`) — see [`references/source-class-registry.md`](references/source-class-registry.md).

### Step 4: Call `source_class.fetch_tier1(url)`

Each source-class module's `fetch_tier1` typically delegates to `scripts/fetch_tier1.fetch_tier1` with any source-class-specific URL rewriting (Reddit, for example, appends `?.json` to comment URLs).

The fetcher returns `{status, body, headers, elapsed_ms, exc}`. **It does not raise on non-2xx** — the caller (this skill) classifies the outcome.

### Step 5: Branch on tier-1 outcome

**Success** (status 2xx, no anti-bot markers in body):

```python
chunks = source_class.parse_to_chunks(fetch_result, gear_ctx={...})
write_chunks(chunks_jsonl_path, chunks, gear_root=gear_root)
```

Each chunk has `tier_used: 1` and `source` set to the matched source class. `write_chunks` automatically computes `cross_source_match_candidates` against all prior chunks (RESEARCH-09) — when a new chunk references a name (gear / artist / external resource) that an already-ingested chunk also references, the field is populated with the deduplicated list of matched names.

**Failure** (any non-2xx, or success body containing an anti-bot challenge):

```python
log_failure(failures_log_path, url, status, body, exc, gear_root=gear_root)
```

One JSON-encoded line appended to `failures.log`. **Do not** attempt tier 2 or tier 3 here. Surface to user at end of run: "N chunks written, M failures logged. Run `/patchbay:research --review-failures` to triage."

### Step 6: Closeout

After processing all URLs:

1. **Report counts:** "Wrote [N] chunks to `<chunks.jsonl path>`. Logged [M] failures to `<failures.log path>`."
2. **Surface cross-source matches:** "[K] new chunks corroborated existing knowledge — see `cross_source_match_candidates`."
3. **Surface failures inline:** list each failure URL + `reason` + `suggested_escalation`, then prompt: "Run `/patchbay:research --review-failures` to escalate, or skip for now?"
4. **Suggest a git commit:**

   > `feat: research [Brand Item] ([N] chunks, [M] failures)`

### Reviewing failures.log via `--review-failures`

When invoked as `/patchbay:research --review-failures`, the skill loads
`<gear_root>/<Brand Item>/knowledge/failures.log`, filters out entries that
already have a later resolution record, and walks the unresolved failures
one at a time. The full flow is documented in
[`references/review-failures-flow.md`](references/review-failures-flow.md);
this section is the load-bearing contract surface.

**Per-failure summary line.** Each unresolved entry prints url + `reason` +
`http_status` + `suggested_escalation`. The user then picks one of four
choices (case-insensitive):

| Choice              | What it does                                                                                |
|---------------------|---------------------------------------------------------------------------------------------|
| `tier-2`            | Real-browser fetch via the Claude in Chrome MCP extension                                   |
| `tier-3`            | System-level Chrome handoff + screenshot + Claude vision; YOU Read the screenshot          |
| `paste`             | Tier 0 — user pastes DOM text; we route it through the matched source class                |
| `skip`              | Append a `user-skipped` resolution; never retry                                             |

**No automatic fallback.** If tier-2's precheck fails (`list_connected_browsers`
returns `[]`) OR the tier-2 fetch raises OR the tier-3 fetch raises, the
loop appends a resolution (`extension-missing` or `tier-error`) and MOVES
ON. It NEVER silently tries a different tier. The user retains agency.

**Precheck for tier-2 is mandatory.** Before the first network call,
`tier2_chrome.precheck_chrome_extension(mcp_tools)` runs
`mcp__Claude_in_Chrome__list_connected_browsers`. Empty result → print install
instructions, append `extension-missing` resolution, continue.

**Resolution records are append-only.** Each user choice appends one new JSON
line of shape:

```json
{"type": "resolution", "url": "...", "resolved_at": "ISO-8601-Z",
 "tier_used": 0|2|3|null, "outcome": "success|user-skipped|extension-missing|tier-error",
 "chunks_written": N}
```

The original failure entry is NEVER rewritten. `load_failures` filters out
any failure whose URL has a later resolution record.

**Tier-3 vision second pass.** `tier3_vision.fetch_tier3` returns a
`screenshot_path` plus an empty `body`. YOU (the SKILL driver) Read that
path, generate the page text from the screenshot, and substitute it into
`fetch_result.body` BEFORE the dispatcher calls `parse_to_chunks`. This is
the only place in the flow where vision-via-Read is the load-bearing
operation; the pure-Python module returns the path and stops.

**Successful escalations feed the same writer.** Tier-2, tier-3, and paste
all dispatch to the matched source class's `parse_to_chunks`, then write
via `write_chunks` — so `cross_source_match_candidates` is populated
automatically against everything already in `chunks.jsonl` (RESEARCH-09).
Every emitted chunk gets `tier_used` matching the escalation tier (2 / 3 / 0).

### Step: Surface cross-source citation recommendations (`--citations`)

When invoked with `--citations <gear>`:

1. Resolve `<gear>` → `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` per Step 1's rules. If the folder or file does not exist, stop with the same gear-not-found guidance as Step 1.
2. Dispatch to `scripts/citations.py`:

   ```bash
   python3 skills/patchbay-research/scripts/citations.py <chunks_path> --gear "<Brand Item>" [--threshold N] [--filter-url URL] [--json]
   ```

3. The script prints recommendations to stdout (markdown by default, JSON with `--json`). The user sees the output directly; nothing is written to disk. Empty results still print a single guidance line and the command exits 0 — silent success is not allowed.
4. To act on a recommendation, the user runs the Plan 04-03 `--verify <gear> <url>` subcommand against the chosen canonical URL.

Full subcommand reference: [`references/citations-flow.md`](references/citations-flow.md).

Threshold semantics (CITATION-02): a recommendation surfaces when the `external_resource` chunk's `citing_chunk_ids` come from at least N DISTINCT `source` values (not raw count). Default N=2; override via `--threshold` flag or `PATCHBAY_CITATION_THRESHOLD` env var (flag wins).

### YouTube two-pass enrichment

YouTube ingestion is a two-pass operation. The first pass (`youtube.parse_to_chunks` + `write_chunks`) writes `multimodal_segment` chunks with a placeholder vision description; the SKILL driver (you) MUST complete the second pass before the research run returns control.

**First pass — what the pipeline already did:**

- `yt_pipeline` invoked yt-dlp + ffmpeg in a per-run tempdir under `tempfile.gettempdir()` (NEVER under `gear_root`).
- For each (caption window, sampled frame) pair, it emitted a `multimodal_segment` chunk with:
  - `content.frame_description == "<<PENDING_READ_TOOL_DESCRIPTION>>"` (literal sentinel placeholder).
  - `provenance.frame_path` set to the absolute on-disk path of the frame `.jpg`.
  - `provenance.deep_link` carrying the `&t=<seconds>s` (or `?t=<seconds>s`) fragment.
- `write_chunks` appended the chunks to `chunks.jsonl` and populated `cross_source_match_candidates`.

**Second pass — what you do now, before exiting:**

For each `multimodal_segment` chunk in this run whose `content.frame_description == "<<PENDING_READ_TOOL_DESCRIPTION>>"`:

1. **Read** the local frame image at `provenance.frame_path` (use the Read tool — it accepts image paths and presents the image visually).
2. **Generate** a one-sentence description of what is visually distinguishable on screen — gear visible, hands on controls, on-screen text/labels, anything the caption alone misses. Keep it factual and falsifiable from the image alone; do NOT speculate.
3. **Call** `write_chunk.update_chunk_field(chunks_jsonl_path, chunk_id, "content.frame_description", <description>)` (from the Plan 01 helper) to overwrite the placeholder. This rewrite is atomic via `tempfile.mkstemp` + `os.replace`.
4. **Continue** until no chunk in the current run still contains the sentinel.

**Tempdir lifetime caveat.** Frame `.jpg` files live in the per-run tempdir, which is cleaned up via `shutil.rmtree` in `parse_to_chunks`'s try/finally. The enrichment loop above runs BEFORE that cleanup returns control. If for any reason `provenance.frame_path` does not exist on disk by the time you Read it (tempdir already cleaned up, file system race), overwrite the placeholder with the string `"frame unavailable"` rather than leaving the sentinel in place. The literal sentinel must NEVER persist in `chunks.jsonl` past the end of a research run.

Full background: [`references/source-class-youtube.md`](references/source-class-youtube.md) § Two-pass model.

## Cross-source corroboration

When `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` already contains chunks (from a prior `patchbay:ingest` manual run or a prior `patchbay:research` web run), `write_chunks` populates `cross_source_match_candidates` on every new chunk automatically (**RESEARCH-09**).

This is a trivial set-intersection: lift named entities (artists, gear models, URLs) from each new chunk, intersect against the same set lifted from all prior chunks. The bidirectional scan handles possessive and abbreviated variants (e.g., a prior chunk's "Rhett Shull" matches a new chunk's "Rhett Shull's review"). No separate ranking pass — the field is set at write time and grows monotonically as more sources are added.

Downstream UI surfaces this as a "corroborated by N sources" badge (see § UI layer notes).

## Error handling

| Situation | Behavior |
|---|---|
| No gear folder for `<gear>` | Stop. Direct user to `patchbay:add-gear` or check folder naming. |
| URL has non-http(s) scheme **or** resolves to a private IP (e.g., `127.0.0.1`, `10.x.x.x`) | Reject with message: "Refusing to fetch {url}: scheme/host not allowed." **Do NOT log to failures.log** — this is a refusal, not a fetch failure. (T-03-01 SSRF mitigation surfaced.) |
| `gear_root` arg resolves to a path outside the configured `gear_root` (path traversal attempt via `..` in gear arg) | Stop: "Refusing path outside gear_root." Do NOT write to disk. (T-03-04 path-traversal mitigation surfaced.) |
| Tier-1 returns 2xx but body is empty / parse yields zero chunks | Log nothing; surface to user: "[url] returned content but produced no chunks — check parser for this source class." |
| Tier-1 timeout (15s) | Append `failures.log` entry with `reason: "timeout"`, `suggested_escalation: "either"`. Continue to next URL. |
| `chunks.jsonl` corrupt (un-parseable line on read) | Refuse to append. Offer to back up to `chunks.jsonl.corrupt.bak` and re-attempt. Mirrors `patchbay:ingest` corrupt-file handling. |
| Network unreachable (no DNS, no route) | Append `failures.log` entry with `reason: "other"`, `suggested_escalation: "either"`. Continue. |
| Source-class `parse_to_chunks` raises | Catch, log to failures.log with `reason: "other"`, `reason_detail` including the exception message. Continue. |
| Unknown host (no `match_url` matches) | Route to generic source class (`REGISTRY[-1]`). It will attempt a best-effort `<h1>` + paragraph scrape. |
| Tier-2 extension not connected (`list_connected_browsers` returns `[]`) | Print install instructions, append a resolution with `outcome: "extension-missing"`, continue to the next failure. NO automatic fallback to tier 3. (T-03-33 — consent bypass mitigation.) |
| Tier-2 / tier-3 fetch raises mid-escalation | Append a resolution with `outcome: "tier-error"` and the tier that was attempted, continue to the next failure. NO automatic fallback to a different tier. |
| User types an unrecognized choice at `--review-failures` prompt | Re-prompt up to 3 times, then default to `skip` with a warning. (T-03-32 — bounded retry.) |

## UI layer notes

These decisions were made with a future hover-citation UX in mind (per project memory: parallel UI notes required in all patchbay specs).

| Decision | UI implication |
|---|---|
| `tier_used` field on every chunk (0–3) | UI surfaces freshness/confidence — tier-1 chunks rendered as "static fetch," tier-2 as "real browser," tier-3 as "vision-verified." Lets the user weight evidence at a glance. |
| `failures.log` is append-only JSONL with grep-friendly fields | UI offers a "review failures" surface that's a direct rendering of this file — same shape Plan 05's CLI uses, no UI-specific data layer. |
| `cross_source_match_candidates` populated at write time | UI shows a "corroborated by N sources" badge per chunk, list-expandable to the prior chunk IDs. Builds the citation-count recommendation feedback loop into the substrate. |
| `/patchbay:research --review-failures` is the interactive escalation surface | UI maps the CLI flow 1:1 — a triage queue with per-entry "escalate to tier 2 / 3 / paste / skip" actions. Same data, same decisions; CLI and UI never diverge. |
| `cross_source_match_note` (optional free-text) | UI renders this inline below the badge as the human-readable explanation of why two chunks corroborate. |
| `provenance.tier_label` (added by tier-2/3 escalations in Plan 05) | UI distinguishes USER_PASTED, AUTO_TIER1, AUTO_TIER2, AUTO_TIER3 chunks visually — same source class, different trust profiles. |
| One JSON object per line, real `json.dumps` encoder | UI streams chunks; grep / jq work directly against the file. No UI-side parser fragility. |
| YouTube `multimodal_segment` chunks carry `provenance.frame_path` + `content.frame_description` (filled by the two-pass enrichment loop) | UI renders the frame thumbnail next to the caption text — the user sees what was on-screen when the caption was spoken (the spike-002 "effect-list-on-screen" moment). The synthesized `frame_description` doubles as the thumbnail's `alt` attribute for screen readers. Any chunk still carrying `<<PENDING_READ_TOOL_DESCRIPTION>>` renders with a "pending vision review" badge so the user can re-trigger the enrichment loop. The same `?t=<seconds>` deep_link affordance applies, jumping the embedded YouTube player to the cited moment. |
| `--review-failures` flow exposes exactly four per-failure choices (tier-2 / tier-3 / paste / skip) with NO auto-fallback | UI renders four explicit buttons per failure row. There is NEVER a "try all tiers" / "auto-escalate" affordance — that would violate the consent contract (T-03-33). When `list_connected_browsers` is empty, the tier-2 button is greyed-out with an inline "install Claude in Chrome extension" link, but tier-3 / paste / skip remain selectable. This is the load-bearing escalation UX — the same data, prompts, and outcomes as the CLI flow; CLI and UI never diverge. |

## Security notes (T-03-01 / T-03-03 / T-03-04 mitigations)

- **SSRF refusal (T-03-01):** `fetch_tier1` rejects non-http(s) schemes and any URL whose host resolves to a private/loopback range — even via DNS rebinding. Refusal surfaces in the error-handling table above; the user sees the refusal message and can correct the URL or paste content manually.
- **JSONL injection (T-03-03):** `write_chunks` and `log_failure` both encode every line via `json.dumps()` on a structured dict. Newlines inside string fields are JSON-escaped; the one-record-per-line invariant cannot be broken by adversarial content in a fetched body.
- **Path traversal (T-03-04):** Both writers validate that the resolved output path lives under the resolved `gear_root` via `Path.resolve().is_relative_to()` (with a 3.8 fallback). A gear arg containing `..` cannot coerce writes outside `<gear_root>/<Brand Item>/knowledge/`.

## What this skill does NOT do

- **Does NOT auto-fall-through tiers.** Tier-2 and tier-3 escalation are user-driven via `/patchbay:research --review-failures` (Plan 05). Cost and latency are real; the user retains agency.
- **Does NOT scrape entire sites.** Patchbay is gear-anchored. One URL at a time, one gear at a time.
- **Does NOT re-fetch existing chunks.** Append-only. To refresh, the user deletes the relevant chunks first or runs `/patchbay:research --review-failures` for a re-attempt.
- **Does NOT write to `chunks.jsonl` from any path but `write_chunks`.** Hand-authored chunks bypass the ID-generation, schema validation, and cross-source-match contract.
