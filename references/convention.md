# Patchbay: Folder Convention Detection

## Reading configuration

1. Look for `patchbay.yml` at the project root (the directory Claude was invoked from).
2. If found, parse it for path overrides. All fields are optional; defaults apply when absent.
3. If not found, use defaults.

## Default paths

| Purpose | Default | patchbay.yml key |
|---|---|---|
| Gear inventory root | `Gear/` | `gear_root` |
| Software inventory root | `Software/` | `software_root` |
| Song research output | `Songs/` | `songs_root` |
| Artist profiles | `Artists/` | `artists_root` |
| Purge/sell list | `Purge.md` | `purge_list` |

## Convention signals

A **Pedalxly-shaped** project:
- Has a `Gear/` folder whose immediate subdirectories are named `<Brand Model>/` (e.g., `Chase Bliss MOOD MkII/`)
- Each subfolder contains `GearProfile.md` with YAML frontmatter

A **minimal / custom** project: only `patchbay.yml` present, pointing at arbitrary paths.

A **flat** project: no structured gear folder. Treat as empty inventory.

If neither `Gear/` nor `patchbay.yml` is found: note "No gear inventory found" in Applied and recommend `patchbay:soundcheck`.

## Song output path

Song research writes to:
```
<songs_root>/<Artist Display Name>/<song-slug>/SongProfile.md
```

- **Artist folder:** the canonical display name, preserving capitalization as the user typed it.
- **Song slug:** lowercase, spaces → hyphens, punctuation removed.

Examples:
- "Creep" by Radiohead → `Songs/Radiohead/creep/SongProfile.md`
- "Black Hole Sun" by Soundgarden → `Songs/Soundgarden/black-hole-sun/SongProfile.md`
- "One More Time" by Daft Punk → `Songs/Daft Punk/one-more-time/SongProfile.md`
- "When the Levee Breaks" by Led Zeppelin → `Songs/Led Zeppelin/when-the-levee-breaks/SongProfile.md`

Create parent directories as needed when writing.
