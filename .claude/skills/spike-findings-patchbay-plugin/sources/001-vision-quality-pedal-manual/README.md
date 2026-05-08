---
spike: 001
name: vision-quality-pedal-manual
type: standard
validates: "Given a real gear manual PDF, when Claude reads it via the Read tool, then output usefully describes knob layouts, signal flow diagrams, response charts, menu screenshots, AND marketing photos — accurate enough for citation-hover RAG"
verdict: VALIDATED
related: []
tags: [ingest, vision, quality, pdf, multimodal]
---

# Spike 001: vision-quality on MPC Sample manual

## What This Validates

**Given** a real gear manual PDF (Akai MPC Sample User Guide v1.3, 67 pages, 6.6MB) with diverse image types — marketing cover, signal-flow diagram, panel diagrams with numbered callouts, individual control close-ups, menu screenshots, control button icons, and parameter envelope curves —
**when** Claude reads the PDF via the native Read tool with the `pages` parameter and produces structured chunks (text + image descriptions) with per-page provenance,
**then** the resulting chunks are accurate and detailed enough that a downstream citation-hover RAG system could quote them as sourced answers and the user could verify the citation by comparing chunk to source page.

This is the highest-leverage unknown for `patchbay:ingest`. If Claude can't usefully describe the panel-diagram on page 16 (40 numbered callouts on a single product photo), the whole gear-anchored knowledge architecture is wrong and we need to pivot.

## Research

| Approach | Tool / library | Pros | Cons | Status |
|----------|----------------|------|------|--------|
| **Native Read tool with `pages`** | Claude Code built-in | Free, mirrors production (the skill *is* Claude), multimodal vision baked in, 20 pages/call | Capped at 20 pages per request — large manuals require batching | **Chosen** |
| Anthropic SDK + base64 PDF | `anthropic` (Python/TS) | Programmable from any script | Costs tokens, requires API key, extra setup | Backup |
| pdftoppm + Vision API per page | poppler + SDK | Per-page granularity, can render at custom DPI | Two-step pipeline, same cost issue | Backup |
| Text-only extract (pdfminer/pypdf) | pdfminer | Fast, free, deterministic | NO vision — fails the requirement (every image matters) | Rejected |

**Chosen approach:** Native Read tool. The production skill *will be* a Claude Code skill, so this *is* the production path. No point benchmarking alternatives until/unless the default approach fails.

**Helper tool:** `pdftoppm` (poppler) renders each page to PNG at 80 DPI for the side-by-side viewer. Not part of the production ingest path — only used here so the user can visually compare source vs chunk.

## How to Run

```bash
open .planning/spikes/001-vision-quality-pedal-manual/viewer.html
```

The HTML viewer loads with chunks inlined as JS — no server needed. Use the page-tab navigation at the top to compare each sample page side-by-side: rendered PDF on the left, the chunks Claude produced on the right. Each chunk shows type (text/image), category (marketing / signal-flow / panel-diagram / screen-screenshot / icon / button-icon), the content, and provenance footer.

## What to Expect

Seven sample pages from the 67-page manual, chosen to cover every image category the seed identified as "matters":

| Page | Category | What's tested |
|------|----------|---------------|
| 1 | Marketing / cover | Pure brand art; vision should categorize and not invent informational content |
| 5 | Signal-flow diagram | Connection routing — gear → cables → peripherals with port labels |
| 15 | Panel diagram (rear) | Photo of rear edge with 9 numbered callouts |
| 16 | Panel diagram (top) | Photo of full top panel with **40** numbered callouts — the killer test |
| 24 | Menu screenshot + button icon | Sample Mode display screen + SAMPLE button icon |
| 25 | Multi-screen screenshot | Side-by-side Trim and Mix screen variants |
| 26 | Parameter / envelope screenshot | Amp Env screen with green ADSR envelope overlay |

20 chunks total (8 image, 12 text). Each chunk has page anchor + rough region for provenance.

## Investigation Trail

**Iteration 1 — sample selection.** Read pages 1-5 first to understand manual structure. Found page 5 (Connection Diagram) immediately as the signal-flow test case and page 1 as the marketing test case. TOC pointed to Features at p15, Operation/Sample Mode at p24, so read 15-17 and 24-26 to capture panel diagrams + menu screenshots.

**Iteration 2 — page 16 challenge.** Page 16 has 40 numbered red callouts on a single top-down product photo. This was the primary stress test. Vision was able to read every numbered callout's label (including secondary/shift functions printed below each control) and group them spatially (top row, mode-button row, knobs, pad play row, transport, etc). The 4×4 pad grid's printed secondary functions ("1 FULL LEVEL", "5 COMPRESSOR", "13 TRIM SAMPLE", etc.) were all readable.

**Iteration 3 — chunk granularity decision.** Faced a choice: one big chunk per page or many small chunks. Picked many small chunks because that's what the citation-hover UX needs — a hover should land on a sentence-level unit, not a whole page. Each page produced 1-4 chunks split by content type and logical block.

**Iteration 4 — provenance schema sketch.** Used `{ manual, page, rough_region }` for the spike. `rough_region` is qualitative (top/middle/bottom/full-page) — coarser than coordinate-bbox but readable and good enough to see if the schema *shape* works. Real production may want bbox, but proving the shape was the spike goal.

## Results

**Verdict: VALIDATED.** User confirmed via side-by-side comparison in the viewer: "pretty accurate spike." Vision quality on the Akai MPC Sample manual is good enough to be the production substrate for `patchbay:ingest`. Page 16 — the killer test with 40 numbered callouts on a single product photo — passed without substantive errors. Page 5's signal-flow diagram was usefully described. Marketing/cover (page 1) was correctly categorized as informationally empty. Menu screenshot tab-states and knob assignments (pages 24-26) were captured accurately.

### Verified findings

- **Native Read tool is the production path.** No need to fall back to the Anthropic SDK + base64 approach. The skill *being* a Claude Code skill means we use what Claude already has.
- **Multiple chunks per page is the right granularity.** Splitting by content type and logical block (image vs text, distinct screenshots, control close-ups) gives citation-hover the unit it needs.
- **`{ page, rough_region }` provenance is sufficient for the spike.** Bounding boxes weren't required for the user to map a chunk back to a region of the source page. Production may want bbox eventually but it's not a v1 blocker.
- **All image categories work:** marketing, signal-flow, panel-diagram (rear with 9 callouts AND front with 40), screen-screenshot, button-icon, parameter-envelope.

### Surprises and qualifications

- "Pretty accurate" is positive but not "perfect" — this spike validated the *approach*, not that every chunk is flawless. Production will need a quality-review loop where the user can correct chunks (which itself becomes valuable signal).
- The user surfaced a new architectural requirement during verification: **chunks must be expandable.** Manuals are the backbone, but external sources (especially YouTube transcripts of tutorials for the gear) should layer on top of and cross-reference the manual chunks. This reinforces the `patchbay:research` design and makes "YouTube transcript ingestion" the next obvious spike.

### Impact on remaining spikes

- **002a/002b (chunk format md vs jsonl):** Still relevant, but lowered priority — the JSON format used in this spike worked fine for the viewer; the production decision can ride on ergonomics rather than feasibility.
- **003 (scale to 100+ page manual):** Now a sanity check rather than a blocker — vision works per-page, batching is just bookkeeping.
- **NEW spike candidate (002 or later): YouTube transcript ingest.** Validate that yt-dlp + transcript extraction can produce chunks compatible with the manual chunks, with timestamp-anchored provenance. This is the next-most-leverage unknown for the *whole* knowledge architecture, not just `ingest`.
