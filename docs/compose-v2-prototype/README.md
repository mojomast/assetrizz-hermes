# compose-v2 (prototype)

Local experiment only. Not in any repo. No commits, pushes, or catalog changes.

A declarative compiler in front of `assetrizz_plugin.scene.compose()`.
The agent describes a scene (style, grid terrain, named slots, feet positions
in grid cells). The engine owns layer bands, y-sort, auto-scale, overlap
checks, density budgets, and reserved HUD docks.

```
specs/ciderlatch.json     agent-facing scene spec
specs/heliox-yard.json
out/ciderlatch.png        re-rendered scenes
out/heliox-yard.png
out/ciderlatch-before-after.jpg
out/heliox-yard-before-after.jpg
out/comparison-sheet.jpg  both games, before | after
out/*-legacy-lint.json    linter on the original v1 scenes
```

Run (CPU-light):

    cd docs/compose-v2-prototype
    nice -n 15 ionice -c2 -n7 python3 render.py

## Spec shape

The agent does not set x, y, z, or (usually) scale. `at` is a grid-cell
feet position. `band` defaults from the asset category.

```json
{
  "id": "ciderlatch",
  "template": "topdown_farming",
  "style": "pixel_32",
  "background": "#6db54a",
  "slots": { "path_mid": [9.5, 8.0], "talk": [13.2, 8.0] },
  "terrain": [
    {"tile": "tiles/floor/grass_base", "rect": [0, 0, 20, 12]},
    {"tile": "tiles/floor/dirt_path_variant_a", "rect": [9, 3, 2, 9]}
  ],
  "place": [
    {"id": "player", "slug": "characters/humanoid/farmer_front", "slot": "path_mid"},
    {"id": "merchant", "slug": "characters/humanoid/merchant_front", "slot": "talk"}
  ],
  "hud": { "title": "CIDERLATCH", "dialogue_text": "..." }
}
```

Templates: `topdown_farming`, `topdown_shooter`, `dungeon_crawler`, `side_platformer`.

## What the compiler does

- Locks one style pack
- Snaps terrain to a grid (whole cells only)
- Anchors sprites by catalog pivot (feet), y-sorts the WORLD band
- Normalizes scale per category when the style is not native pixel
- Rejects or nudges overlapping footprints
- Enforces density budgets
- Reserves HUD docks; lints actors that sit under them
- Draws HUD in screen space with a tiled 9-slice and a solid text well
  (avoids the stretched-panel smear)

`compile_spec()` returns `issues` with `severity`, `code`, `message`, and `fix`
so an agent can revise the spec instead of poking individual layers.
