"""Source-class registry skeleton for `/patchbay:research`.

This file declares an empty `REGISTRY` list. Each source-class plan in
Wave 2 (Plans 02 / 03 / 04 — Reddit, Equipboard, YouTube) adds EXACTLY ONE
line below — `from . import <name>` — and the imported module self-registers
by appending itself to `REGISTRY` at import time.

The pattern is intentional: keeping registration inside each module's own
file lets the three Wave 2 plans land in any order without merge conflicts,
and the registry's final order is determined by import order (which the
generic fallback class — added last — exploits to land at `REGISTRY[-1]`).

See `references/source-class-registry.md` for the full contract.
"""

REGISTRY: list = []

# Plans 02 / 03 / 04 each append exactly one `from . import <name>` line
# below this comment. DO NOT add source-class imports here as part of Plan 01.
from . import reddit  # noqa: F401  (auto-registers via side effect)
