# patchbay

A Claude Code plugin for musicians.

Patchbay is a project-agnostic toolkit that helps musicians use what they
already own. Point it at a folder — gear notes, manuals, research, plugin
inventory — and it adds the skills to inventory, research, design patches,
and chase the tones behind the songs you love.

GAS mode (Gear Acquisition Syndrome) is off by default. The skill is built
to lean on substitution from your existing rig. When you do want to add or
swap, GAS mode surfaces honest acquisition options — including funded swaps
from a sell list you maintain yourself.

## Skills

- **`patchbay:soundcheck`** — first-time setup; detect or scaffold folder convention.
- **`patchbay:add-gear`** — onboard a piece of gear with a structured profile.
- **`patchbay:purge`** — review inventory for sell candidates.
- **`patchbay:ingest`** — pull a manual, article, video, or book into research.
- **`patchbay:research`** — deep gear or technique research.
- **`patchbay:liner-notes`** — research the rig and tone behind a song or artist.
- **`patchbay:dial-in`** — design or recall a patch.
- **`patchbay:midi`** — generate `.mid` / `.syx` files, or send real-time MIDI via a small helper.

## Status

In design. See [docs/specs/](docs/specs/) for the design specs and
[docs/origin.md](docs/origin.md) for the brainstorming history.

The first skill being implemented is `patchbay:liner-notes`.

## Project-agnostic by design

Patchbay reads whatever folder structure you have. It works best with a
[Pedalxly](https://github.com/colfitt/Pedalxly)-style layout
(`Gear/<Brand Item>/`, `Software/<Brand Product>/`, `Songs/<Artist>/<song>/`),
but adapts to flat folders or a custom convention via a per-project
`patchbay.yml`.

Pedalxly is the canonical test case.

## License

[TBD]
