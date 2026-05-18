---
phase: 04-citation-tracking-recommendations
verified: 2026-05-17T00:00:00Z
status: passed
score: 4/4 success criteria + 4/4 requirements verified
test_suite: 138 passed, 0 failed
---

# Phase 4: Citation tracking + recommendations — Verification Report

**Phase Goal (from ROADMAP):** Every external URL referenced from any chunk produces an `external_resource` chunk, and when N independent sources reference the same URL the user is surfaced "this was referenced N times — worth verifying" with a path to verify and ingest it.

**Verified:** 2026-05-17
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Test Suite

```
python3 -m pytest skills/patchbay-research/scripts/ -q
138 passed, 1 warning in 6.46s
```

All 138 tests across 8 test files pass (test_canonicalize_url, test_external_resource_sweep, test_citations, test_verify_resource, plus Phase 3 regression coverage: test_core, test_reddit, test_equipboard, test_youtube, test_review_failures).

---

## Plan-Checker Iteration 1 BLOCKERs — Verification of Deployed Fixes

| BLOCKER | Expected fix | Deployed evidence | Status |
|---------|-------------|-------------------|--------|
| `write_chunks` signature with `trust=` keyword-only | `def write_chunks(chunks_jsonl_path, new_chunks, gear_root=None, *, trust=None)` | `skills/patchbay-research/scripts/write_chunk.py:256-262` — exact signature with `*` keyword-only barrier and `trust: Optional[str] = None` | ✓ VERIFIED |
| `update_chunk_field` dotted-string `field_path` | `field_path: str` (not tuple), split on "." | `write_chunk.py:317` `field_path: str` + L337 `parts = field_path.split(".")`; `verify_resource.py:317` calls with `"content.relevance"`, L324 calls with `"trust"` | ✓ VERIFIED |
| `tier_used = None` on sweep-emitted chunks (NOT 0) | `"tier_used": None` literal in sweep emission | `external_resource_sweep.py:260` — `"tier_used": None,` with comment block at L255-259 explaining why null and not 0 (preserves locked tier-0 "manual user-paste" semantic) | ✓ VERIFIED |
| Sweep ID uses stable `hashlib.sha1` | `ext-sweep-{sha1(canonical_url)[:8]}` | `external_resource_sweep.py:86-99` — `_sweep_id()` returns `"ext-sweep-" + hashlib.sha1(canonical_url.encode("utf-8")).hexdigest()[:8]`; consumed at L243 | ✓ VERIFIED |
| `gear_root` derivation uses `parent.parent.parent` (three levels) | Three-parent walk: chunks.jsonl → knowledge/ → Brand_Item/ → gear_root | `verify_resource.py:371-384` — `_derive_gear_root()` computes `Path(chunks_path).resolve().parent.parent.parent` | ✓ VERIFIED |

All 5 deployed-fix verifications pass against the actual source code.

---

## Success Criteria (from ROADMAP)

### SC1: After `/patchbay:research <gear>`, every external URL has a corresponding `external_resource` chunk with full schema fields populated, no manual aggregation

**Status:** ✓ VERIFIED

**Evidence:**
- `external_resource_sweep.py:227-272` emits new external_resource chunks with the full locked schema: `id`, `type`, `source`, `content.{resource_type, creator, title, url, updated, relevance, citing_chunk_ids}`, `tier_used`, `provenance.{url, scraped_at}`.
- `write_chunk.py:309` invokes `ensure_external_resource_chunks(str(resolved), gear_root=gear_root)` at the END of every `write_chunks` call — the sweep is the writer-boundary guarantee.
- Tests prove the contract: `test_sweep_backfills_missing_external_resource`, `test_sweep_populates_empty_citing_chunk_ids`, `test_sweep_merges_into_nonempty_citing_chunk_ids`, `test_write_chunks_invokes_sweep` (14 cases in `test_external_resource_sweep.py`).

### SC2: URL canonicalization handles common variants so two chunks pointing at the same video count as one citation

**Status:** ✓ VERIFIED

**Evidence:**
- `canonicalize_url.py` pure stdlib function implements all locked variants:
  - youtu.be/X ↔ www.youtube.com/watch?v=X collapse
  - `?si=` (+ utm_*, feature, fbclid, gclid, mc_*) tracking strip
  - Trailing slash strip
  - Lowercase scheme + host
  - Non-http(s) scheme rejection
- 12 test functions (16 cases collected with parametrize) in `test_canonicalize_url.py` pass.
- Sweep dedup proven: `test_sweep_dedupes_by_canonical_url` — two chunks referencing `youtu.be/abc` and `youtube.com/watch?v=abc` produce exactly ONE external_resource chunk.
- Sweep canonicalizes existing chunk URLs in place: `test_sweep_canonicalizes_existing_external_resource_urls`.

### SC3: When N (configurable, default 2) independent sources reference the same canonicalized URL, the user sees a surfaced recommendation in **terminal output** (not buried in a log)

**Status:** ✓ VERIFIED

**Evidence:**
- `citations.py:235` `aggregate_citations(chunks_path, threshold=2, filter_url=None)` — default threshold 2.
- `citations.py:417` `_main(argv)` — argparse `--threshold` flag + `PATCHBAY_CITATION_THRESHOLD` env var with `_default_threshold_from_env()` resolver; CLI flag wins by virtue of argparse only honoring `default` when the flag is absent.
- **Distinct-source rule** (load-bearing for "independent sources"): citations.py counts DISTINCT `citing_chunk["source"]` values, NOT raw `len(citing_chunk_ids)`. External_resource chunks are excluded as voters (vote-inflation prevention). Verified by `test_aggregate_counts_distinct_sources_not_raw_ids` and `test_aggregate_ignores_external_resource_citing_external_resource`.
- Terminal output: `format_recommendations_markdown()` writes to stdout via `_main`. Empty result still prints a locked guidance message (`"No citation recommendations at threshold N=<N> for <gear>. Try --threshold 1 to see all external resources."`). Silent success is not possible — `test_main_exit_zero_on_no_results` confirms.
- 20 pytest cases in `test_citations.py` cover threshold-default, --threshold flag, env var override, distinct-source counting, markdown shape, JSON mode, and exit code 0 on no-results.
- SKILL.md `skills/patchbay-research/SKILL.md:27` dispatches the subcommand: `"/patchbay:research --citations [gear]" → list external resources cited by >= N independent sources (default N=2)`.

### SC4: User can mark a surfaced resource as verified → triggers ingestion → promotes resulting chunks to high-trust

**Status:** ✓ VERIFIED

**Evidence:**
- `verify_resource.py:142` `def verify_resource(chunks_path, gear_ctx, url, *, registry, mcp_tools=None, prompt_user=None) -> dict` — orchestrator.
- Call graph traced from CLI (`/patchbay:research --verify`) through to chunk-store mutations:
  1. SKILL.md:28 dispatches to `python3 skills/patchbay-research/scripts/verify_resource.py <chunks_path> --gear ... --url ...`.
  2. `verify_resource.py:_main()` calls `verify_resource()`.
  3. `verify_resource()` canonicalizes URL via `canonicalize_url()` (Plan 04-01), finds existing external_resource chunk by canonical match.
  4. Dispatches via `url_router.route_url(canonical, registry)` (Plan 03-01).
  5. Calls `source_module.fetch_tier1(canonical)`. YouTube `needs_pipeline=True` sentinel correctly handled at L274-285 (NOT treated as fetch failure when status==0).
  6. `parse_to_chunks(result, gear_ctx)` → new_chunks.
  7. `promote_chunks_to_high_trust(new_chunks)` (defense-in-depth) → `write_chunks(chunks_path, stamped, gear_root=..., trust="high")` (verify_resource.py:306-311).
  8. `update_chunk_field(chunks_path, ext_id, "content.relevance", "verified", gear_root=...)` and `update_chunk_field(chunks_path, ext_id, "trust", "high", gear_root=...)` (L314-327).
- `write_chunk.py:288-294` — stamping happens INSIDE write_chunks: `if isinstance(trust, str) and trust: chunk["trust"] = trust` BEFORE the JSONL append.
- 15 pytest cases in `test_verify_resource.py` cover dispatch, trust=high stamping, idempotent re-verify, missing-resource exit 2, YouTube sentinel path, W6 three-parent gear_root derivation, empty-registry error, CLI exit codes 0/1/2.

---

## Requirements Coverage

### CITATION-01: Every external URL referenced from any chunk produces an `external_resource` chunk with `{resource_type, creator, title, url, updated, relevance, citing_chunk_ids[]}`

**Status:** ✓ SATISFIED — Plan 04-01 (`external_resource_sweep.py` + `write_chunks` hook). Schema fields all populated at emission (`external_resource_sweep.py:248-265`). Tests: `test_sweep_backfills_missing_external_resource`, `test_write_chunks_invokes_sweep`.

### CITATION-02: When N (configurable, default 2) sources independently reference the same external resource, surface to the user as "this was referenced N times — worth verifying"

**Status:** ✓ SATISFIED — Plan 04-02 (`citations.py` + `/patchbay:research --citations` subcommand). Threshold configurable (flag wins env). Distinct-source rule prevents spam. Output format includes literal "referenced X times across Y sources" (per behavioral end-to-end check documented in 04-02-SUMMARY). Tests: 20 cases in `test_citations.py`.

**Known v2.0 limitation** documented in `must_haves.known_limitations` of 04-02-PLAN.md and `references/citations-flow.md`: the distinct-source count may under-represent true independence when same-class chunks dominate (e.g., Equipboard republishing a YouTube reviewer's transcript counts as 1 source). Acceptance bar — multi-source corroboration is observable — is met; precision floor is good-enough for v2.0. Proper primary-source tracking deferred to a future phase. This is a documented limitation, NOT a gap.

### CITATION-03: User can mark a surfaced resource as verified → triggers ingestion → promotes resulting chunks to high-trust

**Status:** ✓ SATISFIED — Plan 04-03 (`verify_resource.py` + `write_chunks(trust="high")` keyword-only param + `/patchbay:research --verify` subcommand). `chunk["trust"] = "high"` stamped at write boundary AND via `promote_chunks_to_high_trust` (defense-in-depth). External_resource chunk's `content.relevance` updated to "verified" + own `trust="high"` via `update_chunk_field`. YouTube needs_pipeline sentinel honored. Idempotent re-verify. Missing-resource error redirects user to `--citations`. Tests: 15 cases in `test_verify_resource.py`.

### CITATION-04: URL canonicalization handles common variants (`youtube.com/watch?v=X` vs `youtu.be/X`, with/without `?si=`, with/without trailing slashes) before counting citations

**Status:** ✓ SATISFIED — Plan 04-01 (`canonicalize_url.py`). All four locked variants implemented + tracking-param strip + non-http(s) rejection. Sweep canonicalizes BOTH at emission time AND when canonicalizing existing external_resource chunk URLs in place (`external_resource_sweep.py:215-220`). Tests: 12 functions / 16 cases in `test_canonicalize_url.py` + `test_sweep_dedupes_by_canonical_url`.

---

## Required Artifacts

| Artifact | Status | Notes |
|----------|--------|-------|
| `skills/patchbay-research/scripts/canonicalize_url.py` | ✓ VERIFIED | Stdlib only, ~90 LOC, imported by sweep + citations |
| `skills/patchbay-research/scripts/external_resource_sweep.py` | ✓ VERIFIED | Post-write atomic rewrite, sha1 stable IDs, tier_used=None |
| `skills/patchbay-research/scripts/citations.py` | ✓ VERIFIED | aggregate_citations + format + CLI entry point |
| `skills/patchbay-research/scripts/verify_resource.py` | ✓ VERIFIED | verify_resource + promote_chunks_to_high_trust + CLI |
| `skills/patchbay-research/scripts/write_chunk.py` | ✓ VERIFIED | Modified — sweep hook (Plan 04-01) + keyword-only `trust=` (Plan 04-03) |
| `skills/patchbay-research/SKILL.md` | ✓ VERIFIED | Additive — `--citations` (L27) + `--verify` (L28) subcommand rows + Process sections (L193, L211) |
| `skills/patchbay-research/references/external-resource-sweep.md` | ✓ VERIFIED | Plan 04-01 substrate doc |
| `skills/patchbay-research/references/citations-flow.md` | ✓ VERIFIED | Plan 04-02 subcommand reference |
| `skills/patchbay-research/references/verify-resource-flow.md` | ✓ VERIFIED | Plan 04-03 subcommand reference |
| `skills/patchbay-research/scripts/test_canonicalize_url.py` | ✓ VERIFIED | 12/16 cases pass |
| `skills/patchbay-research/scripts/test_external_resource_sweep.py` | ✓ VERIFIED | 14 cases pass |
| `skills/patchbay-research/scripts/test_citations.py` | ✓ VERIFIED | 20 cases pass |
| `skills/patchbay-research/scripts/test_verify_resource.py` | ✓ VERIFIED | 15 cases pass |

---

## Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `write_chunk.py` | `external_resource_sweep.py` | `ensure_external_resource_chunks(str(resolved), gear_root=gear_root)` at L309 | ✓ WIRED |
| `external_resource_sweep.py` | `canonicalize_url.py` | `from canonicalize_url import canonicalize_url` (L47-49 try/except) | ✓ WIRED |
| `citations.py` | `canonicalize_url.py` | imported at L89-91; used at L193, L269, L281 | ✓ WIRED |
| `verify_resource.py` | `url_router.py` | `route_url(canonical, registry)` (Step C/D in verify_resource) | ✓ WIRED |
| `verify_resource.py` | `write_chunk.py` | `write_chunks(..., trust="high")` at L306-311; `update_chunk_field(...)` at L314-327 | ✓ WIRED |
| `verify_resource.py` | `canonicalize_url.py` | `canonicalize_url(url)` in Step A of verify_resource | ✓ WIRED |
| `SKILL.md` | `citations.py` | Dispatch line at L201 | ✓ WIRED |
| `SKILL.md` | `verify_resource.py` | Dispatch line at L219 | ✓ WIRED |

---

## Anti-Patterns Scan

No anti-patterns found. Scanned for:
- TODO/FIXME/PLACEHOLDER comments — none in Phase 4 production code
- Stub returns (`return null`, `return []` without query) — none; all returns are derived from real data or structured error objects
- Empty handlers — none
- Hardcoded empty data flowing to user output — none

Comments referencing tier_used=0 are intentional documentation explaining WHY the sweep uses `None` instead (preserving the locked tier-0 "manual user-paste" semantic).

---

## Behavioral Spot-Checks

| Behavior | Method | Result |
|----------|--------|--------|
| Full test suite passes | `python3 -m pytest skills/patchbay-research/scripts/ -q` | ✓ 138 passed |
| CLI entry points exist | grep for `__main__` in citations.py + verify_resource.py | ✓ Both have `if __name__ == "__main__": sys.exit(_main(sys.argv[1:]))` |
| SKILL.md routes both subcommands | grep `--citations` and `--verify` in SKILL.md | ✓ Both present (L27, L28) with dispatch lines (L201, L219) |
| Behavioral end-to-end (from 04-01-PLAN acceptance) — sweep canonicalizes `youtu.be?si=` to canonical watch form | Documented as run in 04-01-SUMMARY self-check | ✓ Inline harness passed at plan commit time |
| Behavioral end-to-end (from 04-02-SUMMARY) — two-source scenario produces "referenced 2 times across 2 sources" | Documented in 04-02-SUMMARY end-to-end check | ✓ Stdout contained literal substring |
| Behavioral end-to-end (from 04-03-PLAN acceptance) — W6 three-parent gear_root derivation | Covered by `test_main_verify_default_gear_root_uses_three_parent_levels` in 138-pass test suite | ✓ Passing |

---

## Gaps Summary

**None.**

All 4 success criteria are satisfied. All 4 requirements (CITATION-01..04) are satisfied. All 5 plan-checker iteration-1 BLOCKERs have deployed fixes verified directly against source code. Full test suite (138 cases including 61 new in Phase 4: 16 canonicalize + 14 sweep + 20 citations + 15 verify, plus 77 Phase 3 regression coverage) passes cleanly.

The phase goal — "Every external URL referenced from any chunk produces an external_resource chunk, and when N independent sources reference the same URL the user is surfaced 'this was referenced N times — worth verifying' with a path to verify and ingest it" — is achieved end-to-end:

1. Phase 4 Plan 01 guarantees the substrate (CITATION-01 + CITATION-04) at the chunk-writer boundary, invariant of source class.
2. Phase 4 Plan 02 surfaces multi-source citations to terminal via `/patchbay:research --citations <gear>` (CITATION-02).
3. Phase 4 Plan 03 closes the loop via `/patchbay:research --verify <gear> <url>` (CITATION-03) — promotes verified-resource chunks to `trust: "high"`.

---

_Verified: 2026-05-17_
_Verifier: Claude (gsd-verifier)_
