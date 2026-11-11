# compose-v2 prototype seed

This directory is a **read-only seed** for the compose-v2 bee wave. It was
copied from the box compose-v2 prototype by the coordinator. Do not
hard-code box or PC absolute paths in plugin code.

Bees must **port and adapt** these ideas into `assetrizz_plugin/compose_v2/`
and the existing `assetrizz_scene` tool:

- Resolve assets through the plugin library (`get_asset`, catalog pivots,
  on-demand fetch already used by `place`). Do not open the box Assetrizz
  SQLite database or any box/PC absolute path.
- Existing `op=place` remains backward compatible (top-left `x,y` plus
  explicit `z` and `scale`). New behavior is opt-in via `op=compose` plus a
  `spec` string.
- Do not bump `plugin.yaml` / `__version__`, do not open a catalog PR, and
  do not mention box, home-directory, or PC user-profile absolute paths,
  or tailnet addresses, in committed plugin code or tests.
- The coordinator may delete this seed directory before merge if it is no
  longer useful. Do not expand it.

Prototype modules vs leases:

| Seed file | Lands in (wave) |
| --- | --- |
| `bands.py` (BANDS, CATEGORY_BAND, SKIP_SLUGS) plus scale/pivot helpers in `assets.py` | CV01 |
| `compile.py` (`compile_spec`, issue shape) | CV02 |
| `hud.py` (docks, tiled 9-slice, text well) plus HUD dock constants | CV03 |
| genre `TEMPLATES` plus lint (overlap, density, docks, wall-as-floor) | CV04 |
