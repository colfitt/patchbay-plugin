# /patchbay:research --verify <gear> <url>

The `--verify` subcommand lets the user mark a surfaced citation recommendation as verified. The flow canonicalizes the supplied URL, locates the existing `external_resource` chunk for it, dispatches downstream ingestion via the existing `url_router` (Plan 03-01) — tier-1 static fetch for articles, the multimodal pipeline for YouTube — and promotes the resulting chunks to `trust: "high"`. CITATION-03 deliverable; the closing brick of the Phase 4 citation loop.

## Prerequisite

- You must have already run `/patchbay:research <gear>` AND `/patchbay:research --citations <gear>`. The URL you pass to `--verify` must already be represented by an `external_resource` chunk in the gear's `chunks.jsonl`; if not, `--verify` exits non-zero (code 2) and tells you to run `--citations` first.

## Invocation

```
/patchbay:research --verify <gear> <url>
```

`<url>` may be any variant — `youtu.be/<id>`, `youtube.com/watch?v=<id>`, with or without `?si=` share-tracking params, with or without a trailing slash. `canonicalize_url` (Plan 04-01) normalizes the input before lookup so every variant lands on the same `external_resource` chunk.

Under the hood, this dispatches to the script:

```
python3 skills/patchbay-research/scripts/verify_resource.py \
    <chunks_path> --gear "<Brand Item>" --url "<url>" [--gear-root <path>]
```

`--gear-root` is optional. When omitted, it is derived from `chunks_path` by walking THREE parent directories up: `chunks.jsonl` → `knowledge/` → `<Brand Item>/` → `<gear_root>`. This matches the canonical on-disk layout produced by `patchbay:add-gear`. If the derived path does not exist as a directory, the CLI exits 1 with a clear `Could not derive gear_root from <chunks_path>. Pass --gear-root explicitly.` message.

## What it does (in order)

1. **Canonicalize the URL** via `canonicalize_url` (Plan 04-01). Non-`http(s)` schemes return `""` and the verify run short-circuits with a structured error.
2. **Locate the external_resource chunk** whose `content.url` canonicalizes to the same form. If no chunk matches, exit 2 with the `--citations`-redirect message.
3. **Dispatch to the matching source class** via `url_router.route_url(canonical, REGISTRY)`. For YouTube URLs, the source class's `fetch_tier1` returns the `{"status": 0, "needs_pipeline": True, ...}` sentinel — the verify flow recognizes this and calls `parse_to_chunks` directly (the multimodal pipeline runs). For articles and other static sources, tier-1 static fetch runs as usual.
4. **Stamp every emitted chunk with `trust: "high"`** at the chunk-dict top level. This happens at two levels:
   - `promote_chunks_to_high_trust(chunks)` deep-copies the new chunks and sets `chunk["trust"] = "high"` before they touch the writer.
   - `write_chunks(chunks_path, stamped, gear_root=..., trust="high")` — note the deployed positional order: `chunks_path` first, list second, `gear_root` keyword, `trust` keyword-only (added by Plan 04-03). The writer's trust= path is defense-in-depth.
5. **Update the external_resource chunk** atomically via two `update_chunk_field` calls (Plan 03-01's helper; dotted-string `field_path`, path-first positional):
   - `update_chunk_field(chunks_path, ext_id, "content.relevance", "verified", gear_root=...)`
   - `update_chunk_field(chunks_path, ext_id, "trust", "high", gear_root=...)` — single-segment `"trust"` works even when the chunk has no prior `trust` key (verified against `write_chunk.py` L309-L329: `parts[:-1]` is empty, the parent-walk loop is skipped, the leaf assignment sets `chunk["trust"] = "high"` directly).
6. **The Plan 04-01 post-write sweep** runs at the end of step 4 (it is called from inside `write_chunks`), ensuring `citing_chunk_ids` on the external_resource includes any newly-added chunks that reference the URL.

## The trust flag (locked at v2.0)

- `chunk["trust"]` is a top-level key on the chunk dict.
- Allowed values at v2.0: `"high"` (set by `--verify`) | absent (default).
- This is an **additive** field on the chunk schema (per spike-findings § "All chunk types share a common shape... Source-specific fields are additive, never divergent"). Existing chunks without `trust` remain valid; downstream consumers MUST treat missing as "not promoted" rather than as a failure.
- Only `verify_resource` sets `trust="high"`. No source-class parser self-promotes its own chunks (T-04-14 mitigation).

## Idempotency

Re-running `--verify <gear> <url>` for the same URL is safe.

- The canonical URL is unchanged across runs.
- The external_resource chunk's `relevance`/`trust` fields are written with the same values; `update_chunk_field` is atomic via `tempfile.mkstemp` + `os.replace`, so a re-run is a no-op effect on those two fields.
- Downstream ingestion DOES re-fetch — the user explicitly re-invoked `--verify`, so fresh data is the right behavior. Newly emitted chunks get `trust: "high"`.
- `chunks.jsonl` grows monotonically; the Plan 04-01 post-write sweep dedupes at the external_resource layer (one chunk per canonical URL, citing_chunk_ids merged).

## Errors

| Exit code | Condition | Message |
|-----------|-----------|---------|
| 0 | Success | `Verified <url>: added N chunks at trust=high; external_resource <id> marked relevance=verified.` |
| 1 | Fetch failed OR gear_root derivation failed | `Fetch failed: HTTP <code>` OR `Could not derive gear_root from <chunks_path>. Pass --gear-root explicitly.` |
| 2 | Missing external_resource | `No external_resource chunk found for <url>. Run /patchbay:research --citations <gear> first to see what's actually been referenced.` |

The empty-registry case (no source class matches and no generic fallback) also exits 1 with a structured error naming the canonical URL.

## Relationship to other subcommands

- `/patchbay:research <gear>` — Plan 03-01..05 — gathers candidate URLs, routes + fetches each at tier 1, writes chunks.
- `/patchbay:research --review-failures` — Plan 03-05 — user-driven escalation of tier-1 failures.
- `/patchbay:research --citations <gear>` — Plan 04-02 — surfaces external resources cited by >= N independent sources.
- `/patchbay:research --verify <gear> <url>` — Plan 04-03 (this doc) — marks a surfaced recommendation verified, re-fetches the URL, promotes resulting chunks to `trust: "high"`.

The intended user flow: run `--citations` to see what's being talked about across multiple sources, then run `--verify` on the URLs you actually want to anchor your knowledge base to. Verified chunks carry a signal that future UI surfaces (the conversational citation-hover skill) can weight in ranking.

## UI layer notes

| Surface | Markdown today | Future UI |
|---|---|---|
| Success message | Single-line stdout: `Verified <url>: added N chunks at trust=high; external_resource <id> marked relevance=verified.` | Toast notification + chunks-table highlight; deep-link to the external_resource row in the citations panel. |
| Missing-resource error | Single-line stderr + exit 2 with the `--citations` redirect | Inline error with a "Run `--citations` first" call-to-action button; the failed URL prefills the verify form so the user can retry once the resource is in the substrate. |
| `trust=high` chunks | `chunk["trust"] == "high"` in `chunks.jsonl` | Visual chip on each chunk card; weight the AI's citation-hover ranking (verified chunks float above unverified ones at the same source/citation count). The conversational UX in Patchbay's roadmap reads this field directly. |
