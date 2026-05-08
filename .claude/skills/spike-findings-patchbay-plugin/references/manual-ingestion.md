# Manual Ingestion (PDF → chunks)

The backbone source class for Patchbay's gear knowledge. Validated in spike 001 against a real, image-heavy 67-page Akai MPC Sample manual including a front-panel diagram with 40 numbered callouts.

## Requirements

- All chunks honor the [chunk schema](./chunk-schema.md) — provenance per chunk, page anchor, image categorization.
- All images in the manual are described — no filtering. Marketing covers, signal-flow diagrams, panel photos, screenshots, parameter charts.
- The skill IS Claude — production uses the Read tool's native PDF support, not a separate vision pipeline.
- Multiple chunks per page is the right granularity for citation-hover.

## How to Build It

### Pipeline

```
Gear/<Brand Item>/manuals/*.pdf
        ↓
   Claude reads PDF in 20-page batches via Read tool with `pages` parameter
        ↓
   For each page, produce 1-4 chunks split by content type and logical block:
     - Text chunks: section headings + body paragraphs as markdown
     - Image chunks: vision-described, categorized, page-anchored
        ↓
   Write to Gear/<Brand Item>/knowledge/chunks.jsonl (append-only)
```

### Read tool usage pattern

```python
# The skill's core operation — for each batch of up to 20 pages:
# Read tool call (in skill prompt):
#   file_path = "/abs/path/to/manual.pdf"
#   pages = "1-20"
#
# Claude sees rendered page images + OCR'd text natively.
# Skill prompt instructs Claude to produce chunks with this shape per page:
#
# {
#   "id": "p016-c01",
#   "type": "image",
#   "image_category": "panel-diagram",
#   "description": "Top-down photo of MPC Sample's full top panel with 40 red numbered callouts. Top row: 13 (MAIN VOLUME knob, top-left)...",
#   "provenance": { "manual": "MPC Sample - User Guide - v1.3.pdf", "page": 16, "rough_region": "top" }
# }
```

### Image categories (set on every image chunk)

| Category | Example |
|----------|---------|
| `marketing` | Cover art, lifestyle photos. Categorize and skip detailed description. |
| `signal-flow` | Connection diagrams, routing illustrations. Describe the routing in prose. |
| `panel-diagram` | Photo of device with numbered callouts. **Describe every callout** — text is on-image and won't be in surrounding paragraphs. |
| `screen-screenshot` | Display state. Describe tab/mode/parameter values literally. |
| `button-icon` | Single-control close-up. Identify which control. |
| `icon` | Inline status icons (battery, charging, etc.) |
| `parameter-envelope` | Curve overlays, response charts. Describe the shape. |

### Side-by-side viewer for human verification (recurring pattern)

Every spike that involves vision quality should ship with a side-by-side viewer for the user to verify accuracy. Pattern in spike 001:

1. `pdftoppm -r 80 -png manual.pdf pages-rendered/page` → renders every page as PNG (only for the viewer; production doesn't need this).
2. Static HTML viewer with chunks inlined as JS const, source page rendered alongside the chunks Claude produced.
3. Served via `python3 -m http.server` configured in `.claude/launch.json`.

See [spike-pattern.md](./spike-pattern.md) for the reusable viewer template.

## What to Avoid

- **Don't pre-extract images via pdfimages then describe each separately.** The Read tool sees the page-rendered context (image position, surrounding text labels) which is lost when extracting images standalone.
- **Don't OCR-only with `pdfminer` or `pypdf`.** Image content is part of the manual's information — pure-text extraction discards it. (Verified explicitly during spike 001 research.)
- **Don't use Anthropic SDK + base64 PDF as the production path** unless you specifically need to run outside Claude Code. The Read tool IS the production path; don't fight against the grain.
- **Don't summarize during ingestion** — preserve verbatim text and image descriptions. Summarization is a downstream concern.
- **Don't skip the marketing/cover image.** Categorize as `marketing` and store a brief description; user explicitly confirmed all images matter.

## Constraints

- **20 pages per Read call.** Batches required for manuals >20 pages.
- **Vision quality is "pretty accurate" — not perfect.** User explicitly noted this during spike 001 verification. Production needs a **human-in-the-loop correction path** where the user can edit chunks the model got wrong. Those corrections are themselves valuable signal.
- **Some scanned manuals may need OCR before vision works well.** Not encountered in spike 001 (publisher PDFs all had embedded text), but watch for it.

## Origin

Synthesized from spike 001 (VALIDATED).
Source files: `sources/001-vision-quality-pedal-manual/README.md`
