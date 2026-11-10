# CV00 — compose-v2 file leases and contracts

Wave: compose-v2. Branch: `feat/compose-v2` off `origin/main` `27efdeb`.
Plugin: `mojomast/assetrizz-hermes` v0.1.0. Catalog pin **#152771 stays pinned**.
Merge target: `feat/compose-v2` only. Never merge to `main`, never tag, never
force-push, never bump the catalog submission, never deploy.

Prototype seed (read-only for every bee): `docs/compose-v2-prototype/`.
Adapt it; do not copy box paths into production code.

Schema baseline at this base (both tools combined):

| Encoding | Tokens |
| --- | --- |
| o200k_base | 931 |
| cl100k_base | 918 |
| chars | 3848 |

`op=compose` plus a single `spec` string field must keep schema growth to a
**few dozen** o200k tokens (target: well under +80; measure with
`python3 evals/measure_schemas.py`). Do not add a nested JSON schema for the
spec body — the field is an opaque JSON string.

Existing `assetrizz_scene` place-based API stays backward compatible. All
current tests (40 collected at this base) must keep passing, plus each bee's
new tests.

## Hard rules for every bee

- Change **only** your leased write paths. Create new files only where listed.
- Write the test first; confirm it fails on the base; then implement.
- Pure, injectable dependencies where possible. Tests must not need the 1.65 GB
  local library or the network; use `tests/fakes.py` / fixtures / injected
  metrics.
- Never print or store secrets. No box, home-directory, or PC user-profile absolute paths, and no
  tailnet strings, in committed files.
- Do not edit `plugin.yaml` version, `__version__`, or `docs/catalog/`
  submission drafts except as explicitly leased (none are leased in this wave).
- Model: `deepseek-v4.1-flash`. Run only your own test file(s) plus the
  commands in your brief.

## Wave A write sets and leases (parallel)

Base: `27efdeb` plus this contracts/seed commit. CV01 and CV03 have no
overlapping write paths.

### CV01 — Layer bands, feet y-sort, per-style auto-scale

- **Write:**
  - `assetrizz_plugin/compose_v2/__init__.py` (new package)
  - `assetrizz_plugin/compose_v2/bands.py`
  - `assetrizz_plugin/compose_v2/assets.py` (metrics, pivot, target_scale;
    library-adapted)
  - `assetrizz_plugin/compose_v2/layout.py` (feet_from_topleft /
    topleft_from_feet, world-band z = band_base + feet_y, default_band)
  - `tests/test_compose_v2_layout.py`
- **Read-only:** prototype seed, `assetrizz_plugin/library.py`,
  `assetrizz_plugin/scene.py` (do not edit), `tests/fakes.py`
- **Do not edit:** `assetrizz_plugin/tools.py`, `assetrizz_plugin/scene.py`,
  HUD files, templates, lint, `plugin.yaml`
- **Acceptance sketch:** BANDS `sky, terrain, decal, world, aerial, hud` with
  stable z bases; `world` is y-sorted by feet pivot (catalog `pivot`, default
  bottom-center); `target_scale` honors style/template `native` vs `target_px`
  per category; characters at a lower feet-y sort behind characters at a
  higher feet-y; existing place API untouched.

### CV03 — HUD docks, playfield reservation, tiled 9-slice, HUD text

- **Write:**
  - `assetrizz_plugin/compose_v2/hud.py` (HUD_DOCKS, playfield_world,
    nine_slice_tiled with optional solid text well, sample_well_color,
    draw_hud, wrap/shadow text helpers)
  - `tests/test_compose_v2_hud.py`
- **Read-only:** prototype `hud.py` / `assets.py` (`nine_slice_tiled`),
  `assetrizz_plugin/scene.py` (do not edit)
- **Do not edit:** tools.py, scene.py, bands/assets/layout, compile, lint,
  templates, plugin.yaml
- **Acceptance sketch:** docks reserve screen-edge margins; `playfield_world`
  returns the remaining world rect; 9-slice **tiles** (does not stretch) the
  center and edges; optional solid well fill for readable text; HUD text
  renders into the well; unit tests use tiny synthetic panels, not production
  PNGs required at collection time.

## Wave B write sets and leases (after Wave A has landed on the branch)

### CV02 — Declarative spec, compile_spec, op=compose (`spec` string)

Depends on: CV01 (and should import HUD playfield helpers from CV03 if
already present; if not, compile without HUD draw and leave a hook).

- **Write:**
  - `assetrizz_plugin/compose_v2/compile.py` (`compile_spec`, Issue dataclass,
    terrain coalesce, place/`at`/`slot` to feet, emit layers with band z)
  - `assetrizz_plugin/tools.py` (add `compose` to `SCENE_OPS`; add a single
    `spec` string property; handle `op=compose`; keep `additionalProperties`
    false; do not add a nested spec schema)
  - `assetrizz_plugin/scene.py` only if a thin hook is required (prefer
    keeping new logic in `compose_v2/` and calling existing create / place /
    render / document APIs). **Must not** change the behavior of existing
    ops (`place`, `tile`, `move`, and the rest).
  - `skills/assetrizz-composer/SKILL.md` (document `op=compose` and `spec`)
  - `tests/test_compose_v2_compile.py`
- **Read-only:** CV01 modules, CV03 `hud.py` (call `draw_hud` after world
  render when a spec includes `hud`), prototype `compile.py` / specs,
  `evals/measure_schemas.py`
- **Do not edit:** lint.py, templates.py, plugin.yaml, catalog drafts
- **Acceptance sketch:** `spec` is a JSON string (template name, terrain,
  placements, optional hud). `compile_spec` returns a scene document plus
  `issues`. `op=compose` compiles, loads/creates the scene, and can render.
  Place-based ops unchanged. Schema o200k growth is a few dozen tokens vs
  931. Existing tests still pass.

### CV04 — Lint pass and genre templates

Depends on: CV01, CV02, CV03.

- **Write:**
  - `assetrizz_plugin/compose_v2/templates.py` (`TEMPLATES` for
    `topdown_farming`, `topdown_shooter`, `dungeon_crawler`,
    `side_platformer`: compose size, grid, tile size, scale mode, target_px,
    density budgets, HUD dock parameters)
  - `assetrizz_plugin/compose_v2/lint.py` (overlap, density budgets, actors
    in docks, wall-as-floor, off-canvas, style mixing, layer cap,
    template-aware; Issue objects with `severity`, `code`, `message`,
    `subject`, `fix`; `lint_legacy` for v1 documents)
  - `assetrizz_plugin/compose_v2/compile.py` — **only** a small hook: after
    compile, call lint and merge issues; do not rework compiler layout.
  - `tests/test_compose_v2_lint.py`
- **Read-only:** bands, assets, layout, hud, tools.py, scene.py, skill,
  prototype lint/templates in `bands.py` / `compile.py`
- **Do not edit:** tools.py schema, plugin.yaml
- **Acceptance sketch:** each named template exists and is mergeable;
  lint emits structured issues with a `fix` hint; overlap/density/dock/
  wall-as-floor cases covered by tests; `compile_spec` reports those issues
  without changing the existing place API.

## Overlap check

| Packet | Collides Wave A? | Collides Wave B? | Notes |
| --- | --- | --- | --- |
| CV01 | No — new layout modules only | CV02/CV04 consume, do not rewrite | scene.py / tools.py off-limits |
| CV03 | No — hud.py only | CV04 reads docks; CV02 may call draw_hud | |
| CV02 | After A | Owns compile.py + tools/skill; CV04 may add a lint hook only | schema budget |
| CV04 | After A+CV02 | lint/templates; compile.py hook only | |

No path appears in two Wave A write sets. Wave B is sequential if both
would touch `compile.py`: land CV02 first, then CV04's hook.

## Coordinator (not leased to bees)

- Feature branch, push, secret-scan, PR (no merge/tag/release/deploy).
- Integrate, run the full test suite, measure schemas, author any missing
  fake-game specs (`gablewalk`, `gloamhollow`), re-render all four scenes
  via `op=compose`, build the comparison sheet, attach before/after images
  to the PR.
- Catalog #152771 stays pinned.
