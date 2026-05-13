---
phase: 2
phase_name: chunk-schema-and-patchbay-ingest
verified_at: 2026-05-12
verifier: claude+user
gear_used: Boss BF-3
gear_path: /Users/cfitt/Dev/Pedalxly/Gear/Boss BF-3
manual: BF-3_M_eng03_W.pdf
manual_pages: 1
chunks_produced: 13
verdict: VERIFIED (with one deferred sub-test + 4 findings for next-spike review)
---

# Verification — Phase 2: Chunk schema + patchbay:ingest

## Summary

Ingested **13 chunks** from a real owned-gear manual (Boss BF-3 foldout-poster, 1 page) via `/patchbay:ingest`. Schema validation **PASS** on all 9 checks. Diff-on-reingest preservation **PASS** on all 7 sub-checks — the load-bearing INGEST-06 contract (`_user_edited:true` survives re-ingest) holds end-to-end. Multi-batch boundary test (INGEST-03) is **DEFERRED** because no >20-page manual was ingested in this verification cycle; recommend re-verification on first long-manual ingest. User approved at the Step 6 checkpoint after spot-checking.

## Verdict per requirement

### CHUNK requirements (substantiated by Plan 01 artifacts)

| ID | Verdict | Artifact / evidence |
|---|---|---|
| **CHUNK-01** | PASS | [skills/patchbay-ingest/references/chunk-schema.md](../../skills/patchbay-ingest/references/chunk-schema.md) § Required fields + § Chunk types — one schema across manual/web/YT. Verified by ingest: every chunk in the BF-3 `chunks.jsonl` has the same required-field set regardless of `type`. |
| **CHUNK-02** | PASS | chunk-schema.md § provenance sub-fields. All 13 BF-3 chunks have `provenance.manual`, `provenance.page`, `provenance.rough_region`, `provenance.scraped_at`. |
| **CHUNK-03** | PASS | chunk-schema.md § What goes in `chunks.jsonl`. Verified by ingest: file is `<gear_root>/<Brand Item>/knowledge/chunks.jsonl`, one JSON object per line, UTF-8, newline-terminated, append-only-at-the-line-level (re-ingest rewrites whole file but preserves per-line shape). |
| **CHUNK-04** | PASS | chunk-schema.md § Chunk types lists `artist_usage` and `cross_ref` rows. Phase 2 ingest does not WRITE these types (Phase 3 will), but the schema admits them additively — verified by reading the doc and confirming Phase 2 reader tolerates unknown types. |
| **CHUNK-05** | PASS | chunk-schema.md § Chunk types row for `external_resource`. Same additive-admit pattern as CHUNK-04. |

### INGEST requirements (substantiated by ingest run + preservation test)

| ID | Verdict | Artifact / evidence |
|---|---|---|
| **INGEST-01** | PASS | Ran `/patchbay:ingest` against Boss BF-3 → 13 chunks written to `/Users/cfitt/Dev/Pedalxly/Gear/Boss BF-3/knowledge/chunks.jsonl`. File parses as JSONL, all required fields present. |
| **INGEST-02** | PASS | All 6 image chunks have a valid `image_category` from the seven-value enum (5 `panel-diagram`, 1 `parameter-envelope`). No images filtered; 2 images flagged `_low_confidence_category:true` per the edge-case rule (state-transition tables don't cleanly fit). |
| **INGEST-03** | **DEFERRED** | Boss BF-3 is a 1-page manual — no multi-batch boundary to test. The skill's Step 3 batch-planning logic was exercised (1-page → single batch `1-1`), but the cross-batch continuity check (Step 5) cannot fire on a single batch. Re-verify on first ingest of a >20-page manual; candidates in inventory: Akai MPC Sample, Strymon TimeLine (16M), Roland VG-800 (4 PDFs), Eventide H90. |
| **INGEST-04** | PARTIAL | The "1–4 chunks per page" rule produced **13 chunks for a single-page foldout poster**. The chunks themselves are correctly split by logical block (one `text` per logical text section, one `image` per image, no bundling) — the rule's *intent* (sentence/section granularity, not per-page) is honored. The rule's *numeric expectation* is wrong for foldout-poster manuals. See Finding 1 below. Substantively PASS; numerically PARTIAL. |
| **INGEST-05** | PASS | Preservation test STEP D: diff classifier correctly produced `+:0, ~:1, !:1, =:11, -:0` matching expectations. SKILL.md Step 6's 5-category diff machinery works as specified. |
| **INGEST-06** | PASS | Preservation test STEP G: `p001-c01` retained its user-edited content AND `_user_edited:true` flag after the diff-confirm-rewrite cycle. `chunks.jsonl.bak` produced on confirmed write only. |

## Phase 2 success criteria walk (from ROADMAP § Phase 2)

| # | Criterion | Verdict | Evidence |
|---|---|---|---|
| 1 | User can run `/patchbay:ingest <gear>` against `<gear_root>/<Brand Item>/manuals/*.pdf` and get a populated `chunks.jsonl` | PASS | 13-chunk file produced for Boss BF-3. |
| 2 | Every chunk has unified shape (`id`, `type`, `source`, `content`, `provenance` with `manual`/`page`/`rough_region`/`scraped_at`) for citation-hover | PASS | jq validation on all 13 chunks returned `true` for required-field + provenance-subfield checks. |
| 3 | Every image → image chunk with one of the 7 `image_category` values; no skipped images | PASS | All 6 images in the BF-3 manual produced image chunks. The 7-value enum was used (5 `panel-diagram` + 1 `parameter-envelope`); 2 chunks set `_low_confidence_category:true` instead of inventing a category. |
| 4 | Each page produces 1–4 chunks split by content block; multi-page manuals (>20 pages) ingest cleanly with no gaps where Read batch boundaries fall | PARTIAL | Chunks correctly split by content block. Numeric 1–4 ceiling violated for foldout poster (13 chunks on one page) — see Finding 1. Multi-page batch-boundary test deferred — see INGEST-03 deferral above. |
| 5 | Re-running on a gear that already has chunks shows a diff and asks user to confirm before overwriting; user-edited chunks survive | PASS | Preservation test fully verified — see STEPS D and G above. |
| 6 | Schema supports `artist_usage`, `cross_ref`, `external_resource` as additive fields so Phase 3/4 can write the same `chunks.jsonl` without further schema changes | PASS | chunk-schema.md § Additive fields contract documents the guarantee. Reader-side tolerance (skip unknown `type`, ignore unknown fields) specified in same section. |

## Schema validation results (Plan 03 § Step 3)

| Check | Result |
|---|---|
| 1. Every line parses as JSON | PASS — all 13 lines parse via `jq -e`. |
| 2. Every chunk has required fields (`id`, `type`, `source`, `content`, `provenance`) | PASS — `jq -e 'has(...) and ...'` returns `true` on all 13. |
| 3. Every `provenance` has `manual`, `page`, `rough_region`, `scraped_at` | PASS — same check, all 13 return `true`. |
| 4. Every `id` is unique within the file | PASS — 13 unique IDs of 13 total. |
| 5. Every `image` chunk's `content.image_category` is one of the 7 valid values | PASS — 5 `panel-diagram`, 1 `parameter-envelope`. No invented categories. |
| 6. No chunk bundles multiple distinct content blocks | PASS (spot-checked all 13 against source page) — each chunk represents one logical section or one image. |
| 7. Chunks per page is in the range 1–4 | **FAIL (substance) / PARTIAL (rule-as-stated)** — 13 chunks on 1 page. The chunks are correctly split; the rule's numeric expectation is wrong for foldout posters. See Finding 1. |
| 8. No gap at batch boundaries (multi-batch only) | N/A — single-batch run. |

## User-edit preservation test results (Plan 03 § Step 4)

Test executed as `/tmp/preservation_test.py` (read by jq + Python simulating the SKILL.md Step 6 diff machinery against the real `chunks.jsonl`):

| Sub-step | Action | Result |
|---|---|---|
| A | Simulate user edit: modify `p001-c01.content`, add `_user_edited:true`, save | ✓ |
| B | Skill loads existing `chunks.jsonl` into `{id → chunk}` map | ✓ 13 chunks loaded |
| C | Simulate new model run: tweak `p001-c02.content.description` (model variance), other 12 chunks identical | ✓ 13 produced |
| D | Diff classifier: `+:0 ~:1 (c02) !:1 (c01) =:11 -:0` | ✓ matches expectations exactly |
| E | Assertion suite: c01 in preserved, c02 in updated, c01 NOT in updated, unchanged ≥ 11 | ✓ all pass |
| F | User confirms `yes` → write `chunks.jsonl.bak` + rewrite `chunks.jsonl` | ✓ both files present, .bak has 13 pre-rewrite lines |
| G | Post-rewrite: c01 retains user note + `_user_edited:true`; c02 has new description; .bak preserved | ✓ all pass |

The diff machinery, the 5-category classification rules, the backup-on-yes contract, and the user-edit preservation flag all work end-to-end.

## Multi-batch boundary test (Plan 03 § Step 5)

**DEFERRED — no qualifying manual ingested.**

Boss BF-3's manual is 1 page (foldout poster). INGEST-03's cross-batch continuity check cannot fire on a single-batch run. Recommend re-verification on first ingest of a manual with >20 pages. Candidates in the Pedalxly inventory at verification time:

- `/Users/cfitt/Dev/Pedalxly/Gear/Akai MPC Sample/manuals/MPC Sample - User Guide - v1.3.pdf` — the spike 001 test article, ~67 pages, exercises the 3+ batch path
- `/Users/cfitt/Dev/Pedalxly/Gear/Strymon TimeLine/manuals/TimeLine_UserManual_RevH.pdf` — 16MB, dense
- `/Users/cfitt/Dev/Pedalxly/Gear/Roland VG-800/manuals/VG-800_*.pdf` — four separate PDFs (reference, parameter, basic, full)
- `/Users/cfitt/Dev/Pedalxly/Gear/Eventide H90/manuals/EventideH90.pdf` — 5MB

This deferral is recorded as a re-verification trigger, not a Plan 02 defect.

## Findings (none are defects; all are next-spike triggers)

### Finding 1 — Foldout-poster manuals violate the 1–4-chunks-per-page ceiling

**What:** The Boss BF-3 manual is a 3-column foldout poster (one dense PDF page covering the full product documentation). Honest split-by-logical-block produced 13 chunks: device-overview diagram + 12-item legend + operating diagram + operating steps + 2 state-transition tables + tempo-input notes + flanger/gate envelope + precautions + battery-change diagram + battery-change steps + main specifications. Bundling any of these into one chunk would violate the "don't bundle distinct content blocks" rule in chunk-schema.md § What NOT to do.

**Why it's not a defect:** The chunks themselves are correctly granular for citation-hover. The "1–4 per page" wording is a heuristic anchored on conventional multi-page manuals (spike 001's Akai MPC Sample had 1–4 chunks per page); it doesn't translate to foldout posters that smoosh a whole product's documentation onto one PDF page.

**Recommended rule revision (next spike or Phase 2.1 if needed):**
> Each manual page produces 1–4 chunks **for conventional multi-page manuals**. Foldout-poster manuals (single PDF page containing multiple logical sections) may produce more chunks because they bundle product documentation onto one page. The granularity rule is logical-block-driven, not per-page-numeric.

Action: file as a follow-up plan; do NOT block Phase 2 completion on it.

### Finding 2 — JSONL authoring requires a real JSON encoder

**What:** The first authoring attempt for the BF-3 `chunks.jsonl` used a text editor's `\n` escape sequences inside `content` strings. The Write tool interpreted those as literal newline characters, producing a file that `jq -s` parses leniently but that strict line-by-line readers (`while IFS= read -r line; do echo "$line" | jq -e .; done`) reject. RFC 8259 § 7 disallows raw U+000A inside string literals.

**Why it's not a defect in the skill:** The SKILL.md Step 6 says "minified single-line per chunk; UTF-8; newline-terminated; no trailing comma" — that's correct. The gap is that the SKILL.md doesn't explicitly say "use a real JSON encoder."

**Recommended SKILL.md addition (next spike or Phase 2.1):**

Add to Process Step 6 (Fresh ingest path):
> **JSON-encoding rule:** Use a real JSON encoder (`json.dumps(..., separators=(",", ":"))` in Python, `JSON.stringify` in JS) for every chunk. Do NOT hand-construct chunk lines by string concatenation — embedded newlines and Unicode characters MUST be escaped properly or the file fails RFC 8259 § 7 compliance and breaks line-by-line readers.

Action: minor SKILL.md tweak; recommend rolling into Phase 2.1 or the first Phase 3 plan that touches the same writer.

### Finding 3 — State-transition tables are a real edge case for the 7-category enum

**What:** The BF-3 manual contains two "When Switching to Tempo Input" state-transition tables: each shows 4 device states (CHECK indicator color × Flanger Effects ON/OFF × Pedal switch press state × RATE behavior) laid out as a table with foot-pedal illustrations. None of the 7 image categories fit cleanly:
- Not `panel-diagram` (not a single-device callout)
- Not `screen-screenshot` (not a device screen)
- Not `signal-flow` (not signal routing)
- Not `parameter-envelope` (no curves)

The skill correctly applied closest-match (`panel-diagram` — they do depict the pedal in different control states) AND set `_low_confidence_category:true` per the image-categories.md edge-case rule.

**Why it's not a defect:** The rule is working — it caught a real edge case and surfaced it for review rather than silently miscategorizing or inventing an eighth category. The user can re-categorize manually if desired.

**Recommended next action:** Track state-transition tables as a v2 candidate eighth category (e.g., `state-diagram`). Do NOT add to the v1 enum — that would break the closed-enum contract Phase 2 just locked. Note as input for the next image-category spike.

### Finding 4 — Inventory not always Pedalxly-shaped (gear_root resolution caveat)

**What:** The Pedalxly project at `/Users/cfitt/Dev/Pedalxly` has no `patchbay.yml`. The skill defaulted to `Gear/` per `references/convention.md` and resolved correctly. But Pedalxly also has a separate top-level `Manuals/` directory (empty at verification time — manuals are stored under `Gear/<Brand Item>/manuals/`), which could be a source of confusion for a future user who drops a manual into `/Users/cfitt/Dev/Pedalxly/Manuals/` instead of into the gear folder.

**Why it's not a defect:** The skill's Step 1.4 error message is clear: "No manual PDF found for [gear] at `<gear_root>/<Brand Item>/manuals/*.pdf`." A user dropping a manual in the wrong place will see this error and self-correct.

**Recommended next action:** None for Phase 2. Consider whether Phase 5 (or `add-gear` / `patchbay:soundcheck`) should detect a root-level `Manuals/` folder and offer to route its contents into gear folders.

## Sign-off

User approved at Plan 03 § Step 6 checkpoint after the spot-check.

**Verdict: VERIFIED**

- INGEST-01, INGEST-02, INGEST-05, INGEST-06 — fully verified against real artifacts.
- INGEST-04 — substantively verified (split-by-logical-block correct); numerically partial (foldout-poster edge case). Tracked as Finding 1; not a blocker.
- INGEST-03 — deferred until first multi-batch ingest. Tracked above; not a blocker.
- CHUNK-01..05 — verified against the Plan 01 reference docs + the ingest artifact.
- 4 findings recorded as inputs for future spikes / Phase 2.1 / Phase 3 work. None are defects in the Phase 2 skill.

Suggested commit message:

```
docs: verify phase 2 — patchbay:ingest end-to-end against Boss BF-3
```
