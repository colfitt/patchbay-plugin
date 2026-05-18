# /patchbay:research --citations <gear>

`--citations <gear>` surfaces external resources cited by at least N
INDEPENDENT sources in the gear's `chunks.jsonl`. It is the load-bearing
user-visible surface of **CITATION-02**: when multiple distinct sources
corroborate the same URL, the user sees a surfaced recommendation in
terminal output (NOT buried in a log file). It builds on Plan 04-01's
substrate guarantee — every external URL in `chunks.jsonl` already has
exactly one `external_resource` chunk with canonical URL and complete
`citing_chunk_ids` — so this subcommand does NOT need to derive the
citation graph; it queries an existing one.

Plan 04-03 (verified promotion) consumes the JSON output of this
subcommand to ingest a chosen recommendation for verification.

## Invocation

```
/patchbay:research --citations <gear> [--threshold N] [--filter-url URL] [--json]
```

The SKILL.md driver resolves `<gear>` → `<gear_root>/<Brand Item>/knowledge/chunks.jsonl`
(see SKILL.md Step 1) and dispatches to:

```
python3 skills/patchbay-research/scripts/citations.py \
    <chunks_path> --gear "<Brand Item>" \
    [--threshold N] [--filter-url URL] [--json]
```

## Threshold semantics (CITATION-02)

- Default **N = 2**. Override via `--threshold N` (CLI flag) or the
  `PATCHBAY_CITATION_THRESHOLD` env var; **the flag wins env**.
- A resource crosses the threshold when its citing chunks come from at
  least N **DISTINCT** `source` values. The raw length of
  `citing_chunk_ids` alone is **not** enough.
- Counter-example: an `external_resource` cited 5 times by 5 reddit
  chunks does NOT trip threshold=2 — that is one source spamming, not
  two independent voices. Two distinct sources (e.g., reddit + equipboard)
  cited the same URL → threshold=2 trips.
- The `external_resource` chunk's OWN `source` field (typically `"sweep"`
  for sweep-emitted chunks, or the matched source-class name for parser-
  emitted ones) is NOT counted toward the distinct-source count. Only
  the sources of its CITING chunks are.
- External-resource chunks citing other external-resource chunks are
  IGNORED. An `external_resource` is a citation TARGET, not a SOURCE —
  counting it would inflate the threshold from inside the citation graph
  itself.

### Known v2.0 limitation

When same-class chunks dominate, the distinct-source rule may under-count
true source independence. Example: an Equipboard page that re-publishes a
YouTube reviewer's transcript is counted as ONE source ("equipboard"),
even though the underlying primary sources are two (Equipboard + the
embedded YouTube reviewer). Proper primary-source-independence tracking
(e.g., a `primary_sources: list[str]` field on each citing chunk capturing
the upstream re-published sources) is **deferred to a future phase**.

The CITATION-02 acceptance bar — "multi-source corroboration is
observable in terminal output" — is met by the distinct-source rule;
the precision floor is good enough for v2.0.

## Output (markdown to stdout)

Default output is a markdown block ordered by descending
`independent_source_count` (with `canonical_url` as the tiebreaker for
determinism). Each recommendation block has:

- Heading line: `## N. <canonical_url> — referenced X times across Y sources`
- `- type: <resource_type>` — `"youtube"` | `"article"` | `"reddit-post"`
  | `"image"` | `"other"` (the sweep's authoritative classification per
  Plan 04-01).
- `- creator: <creator>` (only when non-empty)
- `- title: <title>` (only when non-empty)
- `- citing chunks:` followed by indented lines of the form
  `  - [<source>] <chunk_id> — "<excerpt>"` where excerpt is up to ~80
  characters around the URL match in the citing chunk's content (with
  `"..."` truncation markers on the bounds).

### Empty result

When no resource crosses the threshold, the command prints a single
guidance line (LOCKED at v2.0 per W3) and exits 0:

```
No citation recommendations at threshold N=<threshold> for <gear>. Try --threshold 1 to see all external resources.
```

This line is the load-bearing observable for CITATION-02 success
criterion 3 ("observable in terminal output, not buried in a log
file"). Silent success is not allowed.

**Why the empty-result message does NOT say "run /patchbay:research <gear>":**
the user has just run `/patchbay:research <gear>` to populate the
substrate that `--citations` queried; suggesting they re-run it would
misdirect them. Lowering the threshold (`--threshold 1`) is the honest
remediation: it shows every external resource with at least one citing
chunk, which is what the user wants when threshold=2 found nothing.

## JSON mode

```
/patchbay:research --citations <gear> --json
```

Emits a JSON array of `Recommendation` dicts (one per surfaced URL) to
stdout. Each dict has keys:

| Key                          | Type | Notes |
|------------------------------|------|-------|
| `canonical_url`              | str  | output of `canonicalize_url` |
| `resource_type`              | str  | `"youtube"` \| `"article"` \| `"reddit-post"` \| `"image"` \| `"other"` |
| `creator`                    | str  | may be `""` |
| `title`                      | str  | may be `""` |
| `independent_source_count`   | int  | the value compared against threshold |
| `citing_chunks`              | list | `{id, source, excerpt}` dicts; sorted by `(source, id)` |
| `external_resource_chunk_id` | str  | stable across re-runs (`ext-sweep-<sha1[:8]>` for sweep-emitted chunks per Plan 04-01) |

Plan 04-03 (`/patchbay:research --verify <gear> <url>`) consumes this
JSON to look up the chosen `external_resource_chunk_id` and apply a
verified-trust upgrade via `update_chunk_field`. The id stability
guarantee (Plan 04-01 W5 mitigation) is what lets `--verify` work across
re-runs without re-deriving the recommendation.

JSON encoding uses `json.dumps(..., ensure_ascii=False, indent=2)`. RFC
8259 escaping rules guard the terminal display surface against
injection via excerpt content (T-04-11 disposition: accept — `json.loads`
on the consumer side is the trust boundary, not `eval`).

## Relationship to other subcommands

| Subcommand                                | Defined by | Role |
|-------------------------------------------|------------|------|
| `/patchbay:research <gear>`               | Plan 03-01..05 | Discover + fetch web sources for `<gear>`; populate `chunks.jsonl` |
| `/patchbay:research <gear> <url>`         | Plan 03-01..05 | Single-URL research path; bypass discovery |
| `/patchbay:research --review-failures`    | Plan 03-05 | Walk `failures.log` entries; per-entry escalation choice (tier-2 / tier-3 / paste / skip) |
| `/patchbay:research --citations <gear>`   | Plan 04-02 (this doc) | List external resources cited by >= N independent sources |
| `/patchbay:research --verify <gear> <url>`| Plan 04-03 | Mark a chosen recommendation as user-verified; bump trust |

## UI layer notes

(Per project memory: parallel UI notes required in all patchbay specs.)

| Surface              | Markdown today                                                                 | Future UI                                                                                                  |
|----------------------|--------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| Recommendation header | `## N. <url> — referenced X times across Y sources`                            | A clickable card; the URL hyperlinks to the canonical resource; `X times across Y sources` is a badge      |
| Citing chunks list    | Indented lines `  - [<source>] <chunk_id> — "<excerpt>"`                       | Collapsible list; each row is a hover-to-cite affordance jumping to the source chunk + a "show in context" |
| Empty state           | Single line: `"No citation recommendations at threshold N=<N> for <gear>. Try --threshold 1 to see all external resources."` | A muted empty-state panel with a `[Lower threshold to 1]` button; never a "go fetch more" prompt           |
