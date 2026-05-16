"""URL → source-class dispatcher for `/patchbay:research`.

Each source-class module under `skills/patchbay-research/source_classes/`
exposes three callables:
    match_url(url)             -> bool
    fetch_tier1(url)           -> dict
    parse_to_chunks(result, ctx) -> list[chunk]

`route_url` walks a registry of modules and returns the first whose
`match_url` returns True. If none match, the last entry in the registry —
conventionally the generic source class — is returned as the fallback.

This is the integration seam Plans 02 (Reddit), 03 (Equipboard), and 04
(YouTube) plug into: each adds one `from . import <name>` line to
`source_classes/__init__.py` and its module appends itself to `REGISTRY`
on import (self-registration pattern documented in
`references/source-class-registry.md`).
"""

from __future__ import annotations

from types import ModuleType
from typing import Sequence


def route_url(url: str, registry: Sequence[ModuleType]) -> ModuleType:
    """Return the first registry module whose `match_url(url)` returns True.

    If none match, return the last module in `registry` (the generic
    fallback). The caller is responsible for ensuring the registry's last
    entry is the generic class.

    Raises ValueError if the registry is empty — there is no sensible
    fallback in that case.
    """
    if not registry:
        raise ValueError("source-class registry is empty; cannot route URL.")

    for module in registry:
        match_fn = getattr(module, "match_url", None)
        if callable(match_fn) and match_fn(url):
            return module

    # Fallback: the generic source class, conventionally the last entry.
    return registry[-1]
