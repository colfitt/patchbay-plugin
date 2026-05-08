---
title: patchbay:ingest — full-fidelity manual ingestion
trigger_condition: After liner-notes and dialed-in ship; before patchbay:research
planted_date: 2026-05-07
---

# Seed: `patchbay:ingest`

Pull a manufacturer manual into a per-gear knowledge store as **chunks with provenance**. Backbone for the eventual citation-hoverable AI (see [knowledge-architecture note](../notes/knowledge-architecture.md)).

## What it does

User drops a manual PDF into a gear folder, runs `/patchbay:ingest <gear>` (or it auto-fires from `add-gear`). Output: chunked text + image descriptions, each with manual page reference, written to the gear's knowledge store.

## Hard requirement: every image matters

User was explicit: even marketing photos get extracted. No filtering. Categories observed in real manuals:

- Knob layouts / front panel diagrams
- Signal flow / block diagrams
- Spectrograms, EQ curves, response charts
- Menu screenshots
- Lifestyle / marketing photos

A vision model describes each image once at ingest time; the description becomes a chunk anchored to the page it appeared on.

## Open questions

1. **Vision model strategy.** Per-page rendering and multimodal description, or extract embedded images first? PDF page count varies wildly (5 pages to 200+).
2. **Chunk schema.** See knowledge-architecture note — needs to be decided once and reused by `patchbay:research`.
3. **OCR for scanned manuals.** Some older pedal manuals are scans. Detect and route differently?
4. **Re-ingest.** What happens when a manual updates? Replace? Diff?

## Why a seed, not a phase

The chunk schema decision (in the architecture note) needs to land first. Without that, ingest has no output target.
