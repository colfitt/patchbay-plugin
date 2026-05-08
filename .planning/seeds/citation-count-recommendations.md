---
title: Citation-count-driven external resource recommendations
trigger_condition: After patchbay:research has ingested ≥3 sources for any given gear and produced external_resource chunks
planted_date: 2026-05-08
---

# Seed: Citation-count → "you should watch/read this" recommendations

User surfaced this pattern during spike 003 verification:

> "if a tutorial is mentioned multiple times from a deep dive, we tell the user to watch and verify it"

## What it does

When `patchbay:research` ingests multiple sources for a piece of gear (manual + Equipboard + Reddit thread + forum post + …), each source mentions external resources (other YouTube tutorials, articles, related Reddit posts). The schema's `external_resource` chunks (validated in spike 003) track these mentions with provenance back to the citing source.

When citation count for a specific external resource crosses a threshold (probably 2 or 3), the AI surfaces it to the user: *"This Rhett Shull tutorial was independently referenced by 3 of your sources — worth watching."*

The user can then:
- Watch/read the resource
- Mark it verified — promotes it to a high-trust chunk that gets ingested into the gear's knowledge store (via `patchbay:research` or `patchbay:liner-notes` depending on type)
- Mark it skipped — citation count is preserved but no further nudge

This converts passive citation tracking into **active research expansion**, where the AI uses cross-source agreement as a heuristic for "the human should pay attention to this."

## Why this is high-leverage

- Solves the cold-start problem: how do you know which YouTube videos for a piece of gear are worth ingesting? Answer: the ones multiple existing sources agree on.
- It's emergent — falls out of the chunk schema for free, no separate ranking system needed.
- It scales with research depth: as more sources are ingested per gear, recommendations get more confident.

## Open questions

1. **Threshold tuning.** 2 mentions = surface? 3? Likely depends on source quality (a mention from a verified critic review weighs more than a mention from a random Reddit comment).
2. **De-duplication.** The same YouTube URL can appear with/without `?si=` tracking params, with `youtu.be/` short form, etc. Need URL canonicalization before counting.
3. **Negative signal.** What if a resource is *criticized* by multiple sources ("don't watch X, it's wrong about Y")? Should that surface differently?
4. **Domain filtering.** External resources from sketchy domains shouldn't get the citation treatment regardless of count.

## Why a seed, not a phase

Depends on `patchbay:research` shipping first (the chunk store has to exist). Trivial-to-build once it does — citation aggregation is a SQL group-by on the chunk store.
