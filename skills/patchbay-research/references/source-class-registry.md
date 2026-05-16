# Source-Class Registry Pattern

The integration contract Wave 2 plans (02 Reddit / 03 Equipboard / 04 YouTube) consume. Plan 01 ships the empty skeleton; each subsequent plan adds exactly one self-registering module.

## The contract

Every source-class module under `skills/patchbay-research/source_classes/` exposes **three callables**:

| Callable | Signature | Responsibility |
|---|---|---|
| `match_url` | `(url: str) -> bool` | Return `True` if this source class owns the URL. Host-pattern check; cheap, deterministic, no I/O. |
| `fetch_tier1` | `(url: str) -> dict` | Source-class-specific tier-1 fetch. Often delegates to `scripts/fetch_tier1.fetch_tier1`. May apply a cheap-path rewrite (e.g., Reddit's `?.json` suffix). Returns `{status, body, headers, elapsed_ms, exc}`. |
| `parse_to_chunks` | `(fetch_result: dict, gear_ctx: dict) -> list[dict]` | Convert a successful tier-1 fetch into schema-conformant chunks. `gear_ctx` carries gear name, gear knowledge dir, run-level `scraped_at`. |

A module that exposes all three callables AND appends itself to `REGISTRY` on import IS a source class. Nothing else.

## Self-registration

Each source-class module ends with one line:

```python
from . import REGISTRY
REGISTRY.append(__import__(__name__))  # or just: REGISTRY.append(sys.modules[__name__])
```

The conventional, idiomatic form is:

```python
# at module bottom, after match_url / fetch_tier1 / parse_to_chunks are defined
from . import REGISTRY as _REGISTRY  # noqa: E402
import sys as _sys                    # noqa: E402
_REGISTRY.append(_sys.modules[__name__])
```

`source_classes/__init__.py` has one line per Plan 02/03/04 — `from . import <name>` — and the import side-effect populates `REGISTRY`. Order of imports determines `REGISTRY` order. The **generic fallback** module is the LAST import — `route_url` returns `REGISTRY[-1]` when no `match_url` matches.

## How the router uses it

`scripts/url_router.route_url(url, REGISTRY)` walks `REGISTRY` and returns the first module whose `match_url(url)` is True. If none match, it returns `REGISTRY[-1]` (the generic class).

```python
from skills.patchbay_research.source_classes import REGISTRY
from skills.patchbay_research.scripts.url_router import route_url

mod = route_url("https://reddit.com/r/guitarpedals/comments/abc/", REGISTRY)
# mod.match_url, mod.fetch_tier1, mod.parse_to_chunks are all callable.
result = mod.fetch_tier1("https://reddit.com/r/guitarpedals/comments/abc/")
chunks = mod.parse_to_chunks(result, gear_ctx={"gear_root": "...", ...})
```

## Why this pattern

- **Wave-2 plans land independently.** Three plans, three new files, three single-line edits to `__init__.py`. No central registry table to merge-conflict over.
- **No reflection or string lookup.** Modules are Python objects in a list; the router just iterates.
- **Generic fallback is data, not a special case.** Add the generic module last; `route_url` returns it via the same `REGISTRY[-1]` rule used for any unknown host.
- **Source-class swap is one-line.** Replacing the Equipboard module with a stub for testing is one `from . import equipboard_stub as equipboard` line at the import site.

## What the registry skeleton looks like today (Plan 01)

```python
# skills/patchbay-research/source_classes/__init__.py
REGISTRY: list = []

# Plans 02 / 03 / 04 each append exactly one `from . import <name>` line
# below this comment.
```

After Plan 04 ships, the file will be:

```python
REGISTRY: list = []

from . import reddit       # Plan 02
from . import equipboard   # Plan 03
from . import youtube      # Plan 04
from . import generic      # Plan 04 (or earlier) — fallback, must be last
```

## What a module MUST NOT do

- **MUST NOT** mutate other modules' state at import time.
- **MUST NOT** do network I/O at import time.
- **MUST NOT** raise at import time on missing optional dependencies; soft-fail to a `match_url` that returns False.
- **MUST NOT** define a `parse_to_chunks` that writes to disk — that's the caller's responsibility via `scripts/write_chunk.write_chunks`.

## What a module MUST do

- **MUST** define `match_url`, `fetch_tier1`, `parse_to_chunks` at module scope.
- **MUST** self-register on import (`REGISTRY.append(sys.modules[__name__])`).
- **MUST** return chunks that conform to `skills/patchbay-ingest/references/chunk-schema.md` § Required fields — `id`, `type`, `source`, `content`, `provenance` with `scraped_at`.
- **MUST** set `tier_used: 1` on every chunk it produces (this contract is per-source; tier-2/3 escalations in Plan 05 set their own `tier_used`).

## Origin

Synthesized from the chunk-schema contract (Phase 2) and the cheap-by-default tier ladder validated in spikes 003 / 003b / 003c.
