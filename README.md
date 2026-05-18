# patchbay

**A Claude Code plugin for musicians.** Point it at your gear folder and it
adds skills to inventory, research, design patches, and chase the tones
behind the songs you love.

GAS mode (Gear Acquisition Syndrome) is **off by default** — patchbay
leans on substitution from what you already own. Flip it on for honest
acquisition options, including funded swaps from a sell list.

## Shipped

| Skill | What it does | Milestone |
|---|---|---|
| `patchbay:liner-notes` | Research the rig and tone behind a song or artist → `SongProfile.md` | v1.0 |
| `patchbay:dialed-in` | Design or recall a patch → knob positions + signal chain + technique notes | v1.0 |
| `patchbay:ingest` | Turn a gear-manual PDF into a schema-valid, citation-hover-ready `chunks.jsonl` | v2.0 |
| `patchbay:research` | Multi-source web ingest (Equipboard, Reddit, articles, YouTube) with tiered fetch | v2.0 |

**Status:** v1.0 + v2.0 shipped (2026-05-18). 138/138 tests green, 24/24
v2.0 requirements satisfied. Full log in
[`.planning/MILESTONES.md`](.planning/MILESTONES.md).

## Next up (v3.0)

In priority order — top is what we're building next.

1. 🎯 **`patchbay:tone-chase`** — conversational pre-production with **ARLO**. Finish songs with the gear you own. *(design committed → [spec](docs/specs/2026-05-18-patchbay-tone-chase-design.md))*
2. **`patchbay:midi`** — generate `.mid` / `.syx` or send real-time MIDI
3. **`patchbay:soundcheck`** — first-time setup; detect/scaffold folder convention
4. **`patchbay:add-gear`** — structured gear onboarding
5. **Hover-citation UX** — deep-link every sentence to its source
6. **CITATION-02** — primary-source independence (fixes v2.0 same-class under-count)
7. **Multi-gear tone-graph queries** — cross-gear recommendations
8. **Rename** `liner-notes` → `rip-off` *(cosmetic)*
9. **`patchbay:purge`** — review inventory for sell candidates

Full detail + longer arc in [`.planning/ROADMAP.md`](.planning/ROADMAP.md).

## How it works

Patchbay reads whatever folder structure you have. Works best with a
[Pedalxly](https://github.com/colfitt/Pedalxly)-style layout (`Gear/<Brand Item>/`,
`Software/<Brand Product>/`, `Songs/<Artist>/<song>/`), adapts to flat or
custom layouts via a per-project `patchbay.yml`.

Every gear-related skill writes into a unified per-gear knowledge store
at `<gear_root>/<Brand Item>/knowledge/chunks.jsonl` — append-only JSONL,
schema-validated, citation-ready.

## License

[TBD]
