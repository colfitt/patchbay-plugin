---
title: Patchbay knowledge architecture — gear-anchored, citation-traceable
date: 2026-05-07
context: Surfaced during /gsd-explore on the ingest → research flow
---

# Patchbay knowledge architecture

The eventual UX is a conversational AI that answers gear questions and lets the user **hover any sentence in the answer to jump to the source** — the exact manual page, video timestamp, or review paragraph the claim came from. That goal sets hard constraints on every upstream skill.

## Core principles

1. **Knowledge is gear-anchored.** Every chunk of stored knowledge belongs to a specific piece of gear in the user's inventory. Cross-gear knowledge (technique, theory) lives elsewhere and is out of scope here.

2. **The manual is the backbone.** Manufacturer manuals are the highest-trust seed. Everything else (reviews, articles, YouTube transcripts) layers on top and either reinforces or contradicts the manual.

3. **All sources are tagged with importance.** The user can mark a specific review or video as "this one's important" — the AI weights it accordingly when answering.

4. **Provenance is non-negotiable.** Every stored chunk preserves:
   - Source type (manual / review / video / article)
   - Source location (page, timestamp, URL anchor)
   - Importance flag
   - Ingestion date

   Without provenance, the hoverable-citation UX can't be built. Skills that produce summaries without source anchors are useless to the downstream goal.

## What this means for `ingest` and `research`

- `patchbay:ingest` produces **chunks**, not summaries. Each chunk has a manual page reference. Image-heavy manuals need vision-model descriptions stored as chunks alongside the page they appeared on.
- `patchbay:research` extends the same chunk store with web sources. YouTube needs a user-verification gate before a transcript becomes a citable source.
- Both skills write into a **per-gear knowledge store** with a consistent chunk schema.

## Open question

Chunk schema and storage format. Markdown with frontmatter per chunk? JSONL? SQLite? Decision needed before either skill is built — they share the format.
