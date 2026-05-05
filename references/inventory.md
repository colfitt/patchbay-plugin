# Patchbay: Inventory Adapter

## Purpose

Produce a normalized list of owned gear for cross-referencing song research.
Only items with `status: owned` are included.

## How to read gear

1. Determine `gear_root` from `patchbay.yml`, or default to `Gear/`.
2. List immediate subdirectories of `gear_root`. Each is one gear item.
3. For each subdirectory, read `GearProfile.md`. Parse the YAML frontmatter block (content between `---` delimiters at the top of the file).
4. Extract: `name`, `brand`, `category`, `subcategory`, `status`, `tags`.
5. Include only items where `status: owned`.

Repeat for `software_root` (default `Software/`).

## GearProfile.md frontmatter shape (Pedalxly convention)

```yaml
---
name: MOOD MkII
brand: Chase Bliss
category: pedal
subcategory: looper-granular
status: owned          # owned | sold | wishlist | loaned | in-for-repair | broken
tags: []
---
```

## Normalized item shape (what the skill works with)

```yaml
brand: Chase Bliss
name: MOOD MkII
category: pedal          # pedal | software | synth | interface | keyboard | ...
subcategory: looper-granular
path: Gear/Chase Bliss MOOD MkII
tags: []
```

## Matching owned gear to song gear claims

Given a song gear claim (e.g., "DigiTech Whammy IV"), match against inventory at three levels:

| Level | Criteria | Example |
|---|---|---|
| **Exact** | brand + model match (case-insensitive, fuzzy ok) | "DigiTech Whammy IV" vs `brand: DigiTech, name: Whammy IV` |
| **Category** | same subcategory, different brand/model | "DigiTech Whammy" vs owned item with `subcategory: pitch-shifter` |
| **Generic** | same broad category | "tape echo" vs owned item with `subcategory: delay` |

Report the match level per claim. Unmatched = no inventory coverage for that claim.

## Empty inventory fallback

If `gear_root` does not exist and no `patchbay.yml` override is present:
- Do NOT error or abort.
- Continue with an empty owned-gear list.
- In `## Applied`, prepend: "No gear inventory found — results use generic substitutions. Run `patchbay:soundcheck` to configure your folder layout, then `patchbay:add-gear` to add items."
- Use generic category-level substitutions throughout (e.g., "any pitch-shifter" not a specific model).
