---
title: patchbay:research — gear-anchored web research with importance tagging
trigger_condition: After patchbay:ingest ships; chunk schema must exist
planted_date: 2026-05-07
---

# Seed: `patchbay:research`

Extend a piece of gear's knowledge store with sourced web research. Output is **chunks with provenance** in the same schema `ingest` produces — so downstream AI can cite manual and web sources interchangeably.

## What it does

User runs `/patchbay:research <gear>`. Skill pulls reviews, articles, and YouTube transcripts about that specific piece of gear. Each candidate source is presented to the user; user accepts, rejects, or marks "important." Accepted sources are chunked and added to the gear's knowledge store alongside the manual chunks from `ingest`.

## Behavior rules

1. **Always gear-anchored.** Free-text technique questions are out of scope here. The skill takes a piece of gear from inventory; that's it.
2. **Manual is backbone, web is layered on top.** When a web source contradicts the manual, the chunk records the contradiction rather than overwriting.
3. **YouTube needs a user-verification gate.** Transcripts can be wrong, channels can be junk. User reviews each candidate video before its transcript becomes citable.
4. **Importance flag per source.** User can mark "this review is important." Downstream AI weights flagged sources higher.

## Open questions

1. **Source discovery.** Web search? Curated source list per gear category? Both?
2. **YouTube verification UX.** Transcript preview? Watch button? Trust-the-channel shortcut after first verification?
3. **Re-research.** Periodic refresh? User-triggered only?
4. **Contradictions surface.** When a review contradicts the manual, how does that bubble up to the user?

## Dependency

Blocked on `patchbay:ingest` shipping, which itself blocks on the chunk schema decision in the [knowledge-architecture note](../notes/knowledge-architecture.md).
