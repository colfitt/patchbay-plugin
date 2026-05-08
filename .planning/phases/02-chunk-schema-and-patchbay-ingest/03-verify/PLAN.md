# Phase 2 — Plan 03: End-to-end verification against a real manual

**Phase:** 2 (Chunk schema + patchbay:ingest)
**Plan:** 03 of 03
**Wave:** 3
**Depends on:** Plan 01 (schema doc) + Plan 02 (SKILL.md) — both must exist before this plan runs
**Autonomous:** no — has a checkpoint where the user verifies a real ingest run

---

## Goal

Prove the skill works against a real, owned-gear manual end-to-end. Produce a written verification report that walks each Phase 2 success criterion and shows it satisfied by observable artifacts (the actual `chunks.jsonl` produced + the diff output from a re-ingest run).

**Observable outcome:** A populated `chunks.jsonl` exists for at least one real owned-gear item with a manual; a re-ingest run shows the diff prompt and preserves a deliberately-edited chunk; a verification report at `docs/verify/02-chunk-schema-and-patchbay-ingest.md` walks each requirement + success criterion and cites the artifact that proves it.

---

## Files to create

- `docs/verify/02-chunk-schema-and-patchbay-ingest.md` (new — verification report; mirrors the existing `docs/` verification pattern from Phase 1: see git history for `docs: verify phase 1` for shape)

## Files modified at runtime (not "created" in the source-tree sense, but produced by exercising the skill)

- `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` — for the gear chosen in Step 1 below. This is user-folder content, not committed to this repo (gear_root lives in the user's working tree per `references/convention.md`).

## Files NOT to modify

- `skills/patchbay-ingest/SKILL.md` — Plan 02's deliverable. If Plan 03 finds a defect, surface it in the verification report and trigger a follow-up plan; do NOT edit the skill mid-verification (keeps the audit trail clean).
- `skills/patchbay-ingest/references/*.md` — Plan 01's deliverables. Same rule as above.

---

## Concrete steps

### Step 1: Pick a verification target gear

Read inventory per `references/inventory.md`. List owned gear that has at least one PDF in `<gear_root>/<Brand Item>/manuals/`. Prefer:

1. A gear item with a **shorter manual** (≤20 pages) — exercises the single-batch path.
2. If a long manual is also available (>20 pages), run a second pass on it to exercise the multi-batch path. This is the only way to verify INGEST-03 against the real Read-tool boundary behavior.

If no owned gear has a manual on disk, surface this to the user as a precondition failure:
> "Verification requires at least one gear item with a PDF in `<gear_root>/<Brand Item>/manuals/`. None found in inventory. Drop a manual into a gear folder (or specify a path) before continuing."

Do not synthesize a manual. Do not commit a manual to this repo. The user provides one from their own inventory.

### Step 2: Run fresh ingest

Invoke the skill: `/patchbay:ingest <chosen-gear>`. Let it run end-to-end. Capture in the verification report:

- The exact gear chosen and manual filename
- Page count + batch plan announced by the skill
- Total chunks written
- Count of `text` chunks, `image` chunks, low-confidence-category flags
- Path to the produced `chunks.jsonl`

### Step 3: Schema validation pass

For the `chunks.jsonl` produced in Step 2, verify by inspection (script or manual jq):

1. Every line parses as JSON.
2. Every chunk has the five required fields: `id`, `type`, `source`, `content`, `provenance`.
3. Every chunk's `provenance` block has `manual`, `page`, `rough_region`, `scraped_at`.
4. Every `id` is unique within the file.
5. Every `image` chunk's `content.image_category` is one of: `marketing`, `signal-flow`, `panel-diagram`, `screen-screenshot`, `button-icon`, `icon`, `parameter-envelope`.
6. No chunk has more than one logical content block bundled (spot-check 5 random chunks against the source page; if a chunk obviously combines two distinct sections + an image, that's a Plan 02 defect — flag it).
7. Chunks per page is in the range 1–4 (spot-check 5 random pages).
8. For multi-batch manuals: verify no gap at batch boundaries (e.g., page 20 chunks AND page 21 chunks both present).

Document each check + result (pass/fail) in the verification report.

### Step 4: User-edit preservation test

This is the load-bearing test for INGEST-05 + INGEST-06.

1. Pick one chunk from the `chunks.jsonl` produced in Step 2 — preferably an `image` chunk where the model's description has a small inaccuracy you can correct, or any `text` chunk.
2. Edit the chunk's `content` field directly in `chunks.jsonl` (or `content.description` if it's an image chunk). Add `"_user_edited": true` to the chunk.
3. Save the file.
4. Re-run `/patchbay:ingest <chosen-gear>` (same gear).
5. Confirm the skill:
   a. Reads the existing `chunks.jsonl` (does not start fresh).
   b. Produces the diff summary with the five categories.
   c. The edited chunk appears in the `! preserved` count, NOT in `~ updated`.
   d. Asks for confirmation before writing.
6. Type `yes` to confirm the write.
7. Re-read `chunks.jsonl`. Confirm the edited chunk's `content` field is unchanged from your edit (NOT replaced by the model's new output). Confirm `_user_edited: true` is still set.
8. Confirm `chunks.jsonl.bak` exists and contains the pre-re-ingest state.

Document each sub-step + result in the verification report. If any sub-step fails, that is a Plan 02 defect — file a follow-up gap-closure plan rather than fixing it inline.

### Step 5: Multi-batch boundary test (only if a >20-page manual is available in inventory)

Run `/patchbay:ingest` against the long manual. Verify:

1. Skill announces multiple batches in Step 3 of its own process.
2. Final `chunks.jsonl` includes chunks from page 20 AND page 21 (the first batch boundary).
3. If manual has, say, 67 pages: chunks exist for pages 60, 61 (the last-batch boundary at 60→61) and through page 67.
4. No "phantom" chunks at boundaries (a chunk dated to page 21 but actually describing page 20 content) — spot-check.

If no >20-page manual is available, mark this section "deferred — no multi-batch manual in inventory at verification time" in the report. INGEST-03 is then partially verified (single-batch path only); flag for re-verification when the user ingests their first long manual.

### Step 6: Checkpoint — user verifies real-world output

Pause and present the user with:

> **Checkpoint: human verification of ingest output**
>
> I've ingested `[Brand Item]` from your inventory. Before I write the verification report, please:
>
> 1. Open `<gear_root>/<Brand Item>/knowledge/chunks.jsonl`
> 2. Spot-check 5 random chunks against the source manual pages
> 3. Specifically verify:
>    - Image descriptions match what's actually on the page (no hallucinated callouts)
>    - Text chunks preserve verbatim content (no summarization)
>    - At least one panel-diagram chunk enumerates every numbered callout (if the manual has one)
> 4. Tell me: is the ingest quality acceptable for citation-hover use?
>
> Type `approved` to continue, or describe issues. I will pause until you respond.

Do not proceed past this checkpoint without user approval. If the user reports issues:

- Quality issue (vision misreads, hallucinated content): NOT a Plan 03 verification fail — vision quality was already validated in spike 001 as "pretty accurate, not perfect." Note the issue in the report; recommend the user use the `_user_edited` flag to correct.
- Schema / structural issue (missing fields, wrong category, multi-block bundling): IS a Plan 02 defect. File a gap-closure follow-up; do NOT silently fix.

### Step 7: Write verification report

Create `docs/verify/02-chunk-schema-and-patchbay-ingest.md` with sections (mirror the Phase 1 verify shape):

1. **Frontmatter** — `phase: 2`, `verified_at: <date>`, `verifier: claude+user`, `gear_used: <Brand Item>`, `manual: <filename>`.
2. **Summary** — one paragraph: "Ingested [N] chunks from [manual]; schema validation PASS / partial; diff-on-reingest preservation PASS / FAIL."
3. **Requirements walk** — for each of the 11 Phase 2 requirements (CHUNK-01..05, INGEST-01..06): one line stating verdict + the artifact that proves it. Reference Plan 01 for CHUNK-01..05 (anchored in `references/chunk-schema.md`); reference the actual run output for INGEST-01..06.
4. **Success criteria walk** — for each of the 6 success criteria from ROADMAP § Phase 2: one line + verdict + artifact reference.
5. **Schema validation results** — checklist from Step 3 above with pass/fail per check.
6. **User-edit preservation test results** — sub-step-by-sub-step from Step 4.
7. **Multi-batch boundary test** — Step 5 results, OR "deferred — no qualifying manual."
8. **Issues found** — any defects from Step 6 user feedback or Steps 3–5 checks. For each: severity, plan-of-record, follow-up action (gap-closure plan, deferred, accepted-as-known-limitation).
9. **Sign-off** — user `approved` from Step 6, plus your one-line verdict: VERIFIED / PARTIAL / FAILED.

### Step 8: Commit

If verdict is VERIFIED or PARTIAL with no defects requiring re-plan:

```
docs: verify phase 2 — patchbay:ingest end-to-end against [Brand Item]
```

If verdict is FAILED or PARTIAL with defects requiring a follow-up gap-closure plan: do NOT commit a "complete" claim. Surface the gap to the user and propose a Plan 04 (gap-closure) before any further commits.

---

## Verification (of this plan)

Plan 03 succeeds when **all** of these are true:

1. `docs/verify/02-chunk-schema-and-patchbay-ingest.md` exists.
2. The report walks every Phase 2 requirement and every success criterion with a verdict + artifact reference.
3. The user-edit preservation test (Step 4) was actually run against a real `chunks.jsonl` and recorded sub-step-by-sub-step.
4. The user approved at the Step 6 checkpoint OR a gap-closure plan was filed (one of the two — silent skip is not acceptable).
5. The verification verdict is recorded: VERIFIED / PARTIAL / FAILED.
6. If verdict is VERIFIED: a commit message in the format above has been suggested to the user.

---

## Requirements covered

This plan does not introduce new requirement coverage — it *verifies* coverage from Plans 01 and 02. The verification report walks all 11 Phase 2 requirements (CHUNK-01..05, INGEST-01..06) and confirms each is satisfied by an observable artifact.

---

## UI layer notes

| Decision | UI implication |
|---|---|
| Verification report is markdown with structured sections + frontmatter | UI can render verification reports as a per-phase status page; surfaces defects, sign-off, and known limitations |
| User-edit preservation test is part of verification | UI surfaces a "preservation test passed [date]" badge per skill — proves the editing surface (CLI today, UI tomorrow) is honored |
| Issues table format (severity / plan-of-record / follow-up) | UI maps directly to a defects-and-followups list per phase |
| Manual-batch-boundary deferral case | UI shows a "partial verification" badge with the deferred-test reason; nudges re-verification when conditions are met |

---

## Out of scope for Plan 03

- Automated test harness — verification is human-driven against the user's actual gear; an automated harness would require a committed manual (rejected up-thread)
- Performance / cost benchmarking of the skill (chunks-per-minute, vision-token cost) — useful future work, not Phase 2 scope
- Verification of Phase 3 / Phase 4 schema additivity — those phases each get their own verification step that confirms backward-compat with the Phase 2 reader
- Re-running verification after every skill edit — verification is a phase-completion artifact, not a CI gate
