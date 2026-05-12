# Image Categories (closed enum, seven values)

Every `image` chunk produced by `patchbay-ingest` carries an `image_category` from this enum. The list is **closed** — readers (and a future UI) key off these exact string values. New categories require a v2 spike, not an in-flight skill decision.

Hyphens, lowercase. The seven values, spelled exactly:

`marketing` · `signal-flow` · `panel-diagram` · `screen-screenshot` · `button-icon` · `icon` · `parameter-envelope`

## The seven categories

| Category | Definition | Example from a real manual | How to describe it |
|---|---|---|---|
| `marketing` | Cover art, lifestyle photography, branded title cards. The image is there to brand the manual, not to convey controls or routing. | Front cover of the MPC Sample user guide showing the device on a black backdrop with the Akai logo. | One short line: what's in the frame plus brand context. Do not pretend marketing imagery contains technical detail it does not. |
| `signal-flow` | Block diagrams or routing illustrations showing how audio or control signal moves through the device. Arrows, labeled nodes, lines connecting inputs to outputs. | An effects-chain block diagram showing Input → Compressor → EQ → Reverb → Output. | Describe the routing in prose: name each node in order, then list the arrows / branches between them. Do not just say "signal flow diagram." |
| `panel-diagram` | A photo or rendering of the device with **numbered callouts** pointing at controls. The numbers and their meanings are the substance. | A top-down photo of the MPC Sample's full top panel with ~40 red numbered callouts pointing at every knob, button, and jack. | **Enumerate every numbered callout** — the text labels are on-image and won't be in the surrounding paragraphs. If 40 numbers point at 40 controls, the chunk lists all 40 mappings. Don't skip "obvious" ones. |
| `screen-screenshot` | A capture of the device's display showing a particular tab, mode, or parameter state. | The MPC Sample's screen showing the SAMPLE EDIT page with parameters START, END, LOOP, and LEVEL visible. | Describe tab/mode/parameter values literally — read off the screen verbatim where possible. State which page or mode is shown. |
| `button-icon` | A close-up of a single control (one knob, one switch, one jack). Used in manuals when a section is explaining one control in detail. | A close-up of the BLEND knob with arrows indicating CCW = dry, CW = wet. | Identify which control the close-up shows. If arrows / labels appear in the image, transcribe them. |
| `icon` | Small inline status icons or glyphs — battery, charging, MIDI activity, headphone, lock. Typically appear in a "screen icons" reference table in the manual. | A row showing a battery icon, a USB icon, and a MIDI DIN icon with one-line descriptions. | List each icon and its meaning. |
| `parameter-envelope` | Curve overlays, response charts, parameter-vs-time graphics — anything that conveys a *shape* rather than a control layout. | A delay-time chart showing how the TIME knob maps from 0 ms to 2000 ms across its rotation. | Describe the shape: starting value, ending value, curve character (linear / log / stepped), any inflection points. |

## Edge-case rule (mandatory)

**If a manual image does not cleanly fit any of the seven categories, prefer the closest match from the existing seven; do not invent a new category.** Surface the misfit by setting `_low_confidence_category: true` on the chunk and collect those chunks for end-of-run review. Adding an eighth category is a v2 spike, not an in-flight skill decision.

Examples of common edge cases and the closest-match choice:

| Edge case | Closest match | Set `_low_confidence_category`? |
|---|---|---|
| Hand-drawn artist sketch in a manufacturer story page | `marketing` | yes |
| Schematic-style internal circuit diagram | `signal-flow` | yes (it routes signal, but not in the connection-diagram sense) |
| Photo of the device in a player's pedalboard | `marketing` | yes |
| MIDI implementation chart (text-only table that got rendered as an image) | `screen-screenshot` | yes (closest match; flag for review) |
| Patch-cable wiring diagram | `signal-flow` | no (this is the canonical use of `signal-flow`) |

The skill collects every chunk with `_low_confidence_category: true` and reports them at end-of-run so the user can review and re-categorize manually. The UI surfaces these chunks with a "needs review" badge.

## Why no filtering

All seven categories — including `marketing` — are produced and stored. Spike 001 confirmed on a real manual that filtering by category loses information the conversational AI will eventually want (marketing imagery anchors the gear's identity; icon tables answer "what does this icon on the screen mean?"). The seven-value enum is inclusive by design; the UI's job is to render them differently (marketing → de-emphasized; panel-diagram → callout overlay), not the ingest skill's job to drop them.

## See also

[chunk-schema.md](./chunk-schema.md) § Chunk types — how `image_category` slots into the `image` chunk's content shape.
