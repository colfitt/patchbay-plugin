# external_resource_sweep — citation substrate for Phase 4

The `external_resource_sweep` is a post-write idempotent pass that runs at
the end of every `write_chunks` call. It guarantees the load-bearing
citation substrate that Plan 04-02 (recommendations) and Plan 04-03
(verified promotion) build on.

This document locks the canonicalization scope, sweep behavior, and
chunk-level contracts at v2.0. Plans 02 and 03 read this doc and assume
the substrate it describes is satisfied at every chunk write.

## What the sweep guarantees

- **CITATION-01** — every external `http(s)` URL referenced from any chunk
  in `chunks.jsonl` has exactly one corresponding `external_resource`
  chunk after `write_chunks` completes. Each `external_resource` chunk's
  `content.citing_chunk_ids[]` lists the ids of every non-`external_resource`
  chunk whose content (or `provenance.url` / `provenance.deep_link`)
  references that URL.

- **CITATION-04** — URLs stored on `external_resource` chunks are CANONICAL.
  Two chunks pointing at the same resource (`youtu.be/X`, `youtu.be/X?si=tracking`,
  `www.youtube.com/watch?v=X`, `www.youtube.com/watch?v=X&feature=share`,
  trailing-slash variants, host-case variants) collapse to a single
  citation, not several.

## When it runs

- At the end of every `write_chunks(...)` call, AFTER the append loop has
  written the new chunks and BEFORE the function returns.
- The sweep is INVOKED from `write_chunk.py`. It is not a user-facing
  entry point. Tests and operational tooling may call
  `ensure_external_resource_chunks(...)` directly for forensic re-sweeps,
  but normal ingestion goes through `write_chunks`.

## Canonicalization scope locked at v2.0

The sweep dedupes by the output of `canonicalize_url(url)`. The
canonicalization rules locked at v2.0:

- **Reject non-`http(s)` schemes** (`javascript:`, `data:`, `file:`, ...)
  by returning `""`. The sweep discards empty results — these URLs never
  produce an `external_resource` chunk. **T-04-01 mitigation.**
- **Lowercase scheme + host.** `HTTPS://Www.YouTube.com/...` →
  `https://www.youtube.com/...`.
- **YouTube short ↔ long.** `youtu.be/<id>` is rewritten to
  `www.youtube.com/watch?v=<id>`. All YouTube hosts (`m.youtube.com`,
  `youtube.com`, `www.youtube.com`) normalize to `www.youtube.com`.
- **Strip tracking params:** `si`, `utm_source`, `utm_medium`,
  `utm_campaign`, `utm_term`, `utm_content`, `feature`, `fbclid`,
  `gclid`, `mc_cid`, `mc_eid`.
- **Strip a single trailing slash** from a non-root path.
- **Preserve remaining query params**, sorted for determinism.
- **Drop URL fragments** (`#section`). Deep-link fragments live in
  `provenance.deep_link`, not in the citation key.

## Idempotency contract

Running the sweep twice on the same `chunks.jsonl` produces a
byte-identical file the second time. This is verified by
`test_sweep_idempotent`.

Implications:
- Sweep-emitted `external_resource` chunk ids are STABLE across re-runs
  (see "Sweep-emitted external_resource chunks" below).
- `citing_chunk_ids` lists are sorted (deterministic ordering).
- New `external_resource` chunks are id-sorted before append (no
  dict-iteration-order leakage).

## Sweep-emitted external_resource chunks

Chunks created by the sweep (not by a source-class parser) carry:

- `id = "ext-sweep-" + sha1(canonical_url)[:8]` — STABLE across re-runs.
  **W5 mitigation**: a monotonic counter (`ext-sweep-001`, `ext-sweep-002`,
  ...) would re-issue the same id for a DIFFERENT canonical URL when
  discovery order changes between runs. Hash-based ids are round-trip
  stable, which Plan 02's `Recommendation.external_resource_chunk_id`
  depends on. SHA-1 truncated to 8 hex chars yields ~4 billion buckets
  — collision probability across a per-gear `chunks.jsonl` of <10k
  `external_resource` chunks is negligible.

- `source = "sweep"` — preserves audit trail; does NOT masquerade as a
  source-class emission.

- `tier_used = None` (JSON `null`) — **NOT `0`**. The spike-findings
  tier ladder reserves `tier_used=0` for "manual user-paste (escape
  hatch)" — content the USER hand-fed into the system. A sweep-emitted
  chunk is the OPPOSITE of that: it is synthetic, derived from URLs
  already present in OTHER chunks; no fetch happened, no user paste
  happened. `null` is the honest "did-not-fetch" signal. Downstream
  consumers (Phase 3 RESEARCH-01 queries, Plan 02 aggregator, Plan 03
  verify) MUST treat `tier_used is None` as "did not fetch" — equivalent
  to filtering only by `tier_used in {1, 2, 3}` when a fetched-source
  filter is desired.

- `content.resource_type` is the sweep's AUTHORITATIVE classification.
  On merge with an existing `external_resource` chunk emitted by a
  source-class parser, the sweep OVERWRITES the existing
  `content.resource_type`. Rationale: `reddit.py`'s `_classify_url`
  returns `"article"` for `reddit.com/r/X/comments/Y` URLs (it does not
  know the `"reddit-post"` type); the sweep's `_classify_resource_type`
  emits `"reddit-post"` for the same URL. Without an override,
  first-occurrence-wins on merge makes the final classification
  ordering-dependent. The sweep is the single source of truth for
  `resource_type`. Tech debt: a follow-up could extract a shared
  `classify_url` helper used by both `reddit.py` and the sweep; for
  Phase 4 the sweep override is the load-bearing fix.

- `content.creator`, `content.title`, `content.relevance` default to
  `""`; `content.updated` defaults to `None`. Source-class parsers
  (reddit, equipboard) populate these when they emit an
  `external_resource` directly; the sweep does NOT fetch the URL to
  enrich them — that work belongs to Plan 03 (verified promotion) which
  may fetch and update via `update_chunk_field`.

- `provenance.url = canonical_url`; `provenance.scraped_at = sweep run
  timestamp (ISO-8601 UTC)`.

## Threats addressed

| Threat | Mitigation |
|--------|------------|
| T-04-01 (Tampering — non-`http(s)` schemes) | `canonicalize_url` returns `""` for `javascript:` / `data:` / `file:`; the sweep discards empty results. Sweep does NOT fetch — only stores. |
| T-04-02 (Spoofing — source-class duplicate-spam) | Dedup is keyed on canonical URL, not raw URL. A parser spamming `youtu.be/X?si=a`, `youtu.be/X?si=b`, ... cannot inflate `citing_chunk_ids` beyond one entry per CITING chunk. |
| T-04-04 (DoS — partial write) | Atomic rewrite via `tempfile.mkstemp` + `os.replace` (mirrors `update_chunk_field`'s idiom). A crash mid-rewrite leaves the original `chunks.jsonl` intact. |
| T-04-05 (Tampering — `provenance.url`) | `provenance.url` and `provenance.deep_link` are canonicalized + scheme-checked identically to content URLs. A maliciously crafted `provenance.url = "javascript:..."` is dropped. |

## What it does NOT do

- The sweep does NOT fetch URLs. It only INDEXES URLs already present in
  chunks. (Fetching belongs to Phase 3's tier ladder and Plan 04-03's
  verified promotion.)
- The sweep does NOT promote chunks to high-trust status. (That is
  Plan 04-03's job via the `trust=` parameter.)
- The sweep does NOT enrich `creator` / `title` / `updated` fields. (A
  source-class parser populates them on direct emission; Plan 04-03 may
  fetch and update via `update_chunk_field` on verification.)
- The sweep does NOT recurse into `external_resource` chunks for URL
  extraction. An `external_resource` chunk's `.url` is a citation TARGET,
  not a SOURCE — extracting from it would emit a circular self-citation.
- The sweep does NOT touch `cross_source_match_candidates`. That field
  is name-based (verified against `write_chunk.compute_cross_source_matches`
  L135-L186), so dedup-by-canonical-url is naturally safe — dropping a
  duplicate `external_resource` by id never leaves a dangling reference
  in any other chunk's match-candidates list.
