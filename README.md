# Assetrizz for Hermes

<p align="center">
  <img src="docs/banner.jpg" alt="Assetrizz: a dark catalog of original 2D game assets for Hermes" width="1280">
</p>

<p align="center">
  <strong>Search 14,641 original 2D game assets and compose scenes beside the Hermes agent.</strong><br>
  Two compact tools, a dark Desktop pane, and a 15&nbsp;MB scannable catalog.<br>
  The PNGs live in the <a href="https://github.com/mojomast/assetrizz">assetrizz library</a> and are fetched only when you need them.
</p>

Assetrizz is a native [Hermes](https://github.com/NousResearch/hermes-agent) plugin. Ask the agent for a meadow, a ranger, a roadside inn — it searches the catalog, places tiles and props, and renders a PNG. On Hermes Desktop 0.23 or newer, the **Assetrizz** pane live-previews the scene in dark mode while you watch.

This repository is just the plugin (about **16 MB** installed, including a **15 MB** scannable JSONL catalog). The art itself — **14,641** PNGs across **23** style packs, about **1.65 GB** — stays in [mojomast/assetrizz](https://github.com/mojomast/assetrizz) and is pinned at tag **v0.1.0** (commit `05339c228f55ac95ad21b5c947db0c6e36207cd4`). Hashes in the catalog match that tag, so a fetch is verified before it is kept.

- Skill id: `assetrizz:assetrizz-composer` (pass that exact string to `skill_view`)
- Tools: `assetrizz_search`, `assetrizz_scene`
- Requires Hermes `>=0.23.0` (the Desktop pane uses `ctx.rest`)
- Version: `0.2.0` — compose-v2 (`op=compose`, four gameplay templates, layer lint, canvas HUD). See [CHANGELOG.md](CHANGELOG.md).
- License: MIT for the plugin code. The assets remain “original, generated for Kyle Durepos” — see the [library license](https://github.com/mojomast/assetrizz/blob/v0.1.0/pipeline/LICENSE.txt).

<p align="center">
  <img src="docs/example-scene.png" alt="Example scene: a pixel_32 meadow path with an inn, trees, a ranger, and a hare" width="640">
</p>

<p align="center"><em>A 640×320 meadow composed from real <code>pixel_32</code> tiles, trees, a roadside inn, a ranger, and a hare. Scene JSON is in <a href="docs/example-scene.json">docs/example-scene.json</a>.</em></p>

## Asset modes

Set **Settings → Plugins → assetrizz → Asset mode** (`asset_mode` / `ASSETRIZZ_ASSET_MODE`):

| Mode | What happens |
|---|---|
| `on_demand` (default) | Search uses the bundled catalog. When you place, render, or preview an asset, the plugin downloads that one PNG from the pinned GitHub raw URL, verifies its SHA-256 against the catalog, and caches it under the plugin data directory. |
| `local` | Same catalog, but PNGs are read from a library directory you install once — the full 1.65 GB tree, or chosen style packs (for example `pixel_32` is 872 files, about 4 MB; `cozy_cartoon` is 854 files, about 118 MB). Missing files may still be fetched one at a time into that directory. |
| `offline` | No network. Search still works; placing or rendering fails unless the PNG is already in the local library or the on-demand cache. Optional `library_path` / `ASSETRIZZ_LIBRARY` still prefers a complete [library checkout](https://github.com/mojomast/assetrizz) when you have one. |

A bulk download of the library or a style pack is **user-initiated only**. Use the **Download library** button in the Assetrizz pane (size estimate per pack, progress, cancel) or run the CLI yourself. It is not a model tool, and the agent cannot start a 1.65 GB download on its own.

```bash
python -m assetrizz_plugin.cli status
python -m assetrizz_plugin.cli download --style pixel_32
python -m assetrizz_plugin.cli download --all --yes
python -m assetrizz_plugin.cli cancel
python -m assetrizz_plugin.cli remove --yes
```

Downloads use the same pinned tag (`mojomast/assetrizz` `v0.1.0`), SHA-256 verification, at most four concurrent requests, and resume-on-retry (files already on disk whose hash matches are skipped). The pane shows disk usage for the local library and the on-demand cache. **Remove local library** (or `cli remove --yes`) needs confirmation and will not delete a source checkout.

Set **Local library directory** (`local_library_dir` / `ASSETRIZZ_LOCAL_LIBRARY`) if you want the download somewhere other than the plugin data `library/` folder. It must not be a filesystem root.

## Install

```bash
hermes plugins install mojomast/assetrizz-hermes
```

To pin a release, pass the 40-character commit SHA of the [v0.2.0 tag](https://github.com/mojomast/assetrizz-hermes/releases/tag/v0.2.0) as `--ref` (`--ref` does not accept a tag name). The open catalog listing still needs a separate, approved SHA pin.

Search works immediately from the bundled catalog. You do not need a 1.65 GB clone for that. Leave **Asset mode** at `on_demand`, or open the Assetrizz pane and click **Download library** to keep a complete local copy.

If you already have a checkout of [mojomast/assetrizz](https://github.com/mojomast/assetrizz), set **Library path** (`ASSETRIZZ_LIBRARY`) to that folder (`assets/` plus a catalog at `db/assets.db` or `db/assets.db.xz`). Leave it empty to auto-detect a checkout next to this plugin, or set it to `none` to force the bundled catalog. The first search builds a lean SQLite + FTS5 index from `db/assets.jsonl` into the plugin data directory.

Optional: set **Export directory** (`ASSETRIZZ_EXPORT_DIR`) for rendered PNGs. It must not be a filesystem root. The default is the plugin data `exports/` folder, which survives `hermes plugins update`.

The two tools work without the Desktop pane. On Hermes Desktop 0.23 or newer, open the **Assetrizz** pane to watch the current scene, browse assets, inspect layers, and download or remove a local library. The pane talks only through `ctx.rest` — it never dials loopback or attaches authorization headers.

## Scene workflow

Ask the agent to find tiles or characters and lay out a scene, for example:

> Search assetrizz for pixel_32 grass and dirt path tiles, then compose a
> 640×320 meadow with a path, a couple of trees, a ranger, and a hare.
> Render a PNG.

Typical tool flow:

1. `assetrizz_search` `op=stats` or `op=search` with `q`, `style`, `category`.
2. `assetrizz_scene` `op=create` with `width`, `height`, optional `background`.
3. `op=tile` to fill floors or walls; `op=place` for props, characters, foliage.
4. `op=move` / `scale` / `flip` / `layer` / `remove` as needed (`layer=L1`…).
5. `op=render` writes a PNG under the export directory and refreshes the pane.
   The tool result is a **path**, not an embedded image.
6. `op=save` / `op=load` persist scene JSON in the plugin data dir.

Prefer `assetrizz_scene` `op=compose` when the agent should build a scene
from a declarative spec in one step. Pass `spec` as **one JSON string**
naming a `template` (`topdown_farming`, `topdown_shooter`,
`dungeon_crawler`, or `side_platformer`) and a `style`, plus `terrain`,
`place`, and optional `hud`. The compiler coalesces terrain, assigns
bands and y-sorted world z, and returns `issues` (overlap, density,
HUD/playfield, off-canvas, and so on) so you can revise the spec instead
of nudging individual layers. You can still use `op=create` / `op=tile` /
`op=place` for direct layer control.

Every handler returns a JSON string: `{ok: true, ...}` or
`{ok: false, error, code, fix}`.

## Disclosure

- **Network (on demand and user-initiated downloads only).** In `on_demand` or
  `local` mode the plugin may fetch individual PNGs from
  `https://raw.githubusercontent.com/mojomast/assetrizz/v0.1.0/assets/…`
  (the pin is the `asset_ref` setting; default `v0.1.0`, which is commit
  `05339c228f55ac95ad21b5c947db0c6e36207cd4` on the [library repo](https://github.com/mojomast/assetrizz)).
  Requests use the Hermes SSRF guard (`create_ssrf_safe_client`,
  `follow_redirects=False`, `trust_env=False`), allowlist only that host and
  `assets/` prefix, cap the body at 5 MiB, time out, and refuse off-host
  redirects. Each file is checked against the SHA-256 stored in the catalog;
  a mismatch is not kept. There are no credentials and `requires_env` is empty.
- **Bulk downloads are not a tool.** Only the pane button or
  `python -m assetrizz_plugin.cli` can start a library or style-pack download.
  A running job can be cancelled; verified files stay on disk so you can
  resume. A background thread exists only while that user-started job runs.
- **Offline / local files.** `offline` mode never touches the network. An
  optional complete checkout of the library repo (`library_path` /
  `ASSETRIZZ_LIBRARY`) is used first when present. Paths are confined after
  symlink resolution. Tool arguments cannot point the plugin at an arbitrary
  path or a filesystem root. An extra export directory must be set by you
  (Settings or `ASSETRIZZ_EXPORT_DIR`), never by a model argument, and must
  not be a filesystem root.
- **Writes.** Scene JSON, JPEG previews, rendered PNGs, the built
  catalog (from the JSONL source), the on-demand cache, and (if you download it) the local library
  are written under the plugin data directory and, if you set them, the
  Export directory or `local_library_dir`. Writes also honour Hermes
  `file_safety` when the host provides it. Removing a local library from the
  pane requires confirmation and will not delete a source checkout.
- **Untrusted catalog text.** Asset names, tags, and descriptions are treated
  as data, not instructions (control characters are stripped in tool results
  and the pane uses text nodes, not HTML).
- **No secrets** are logged or printed. No subprocesses are spawned.

The installed plugin (this repository, including the 15 MB scannable JSONL
catalog) is about 16 MB. Committing the uncompressed library SQLite file was
not an option: that snapshot is 147 MB and is mostly generation-pipeline
tables this plugin never queries, and a `.db` is still a binary. The JSONL
holds only the fields search and compose need (one asset per line) so a
catalog reviewer can read every record. A lean SQLite + FTS5 database is
built in the plugin data directory on first search, typically in a couple
of seconds, and is rebuilt if the source hash changes. A full local library
download is about 1.65 GB plus the catalog; individual style-pack sizes are
listed in the pane.

This repo was split from [`plugin/`](https://github.com/mojomast/assetrizz/tree/v0.1.0/plugin)
in [mojomast/assetrizz](https://github.com/mojomast/assetrizz) (history preserved
via `git subtree split`). Asset URLs and hashes still point at that library’s
`v0.1.0` tag.

## Develop

```bash
pytest -q tests
python evals/measure_schemas.py
python desktop/build_plugin.py   # rebuild desktop/plugin.js
hermes plugins doctor . --ci
hermes plugins validate . --install-deps
```

Standalone / mock-host tests cover registration, FTS search, path confinement,
Pillow compositing, JSON handler envelopes, on-demand fetch / local install
with a mock HTTP fetcher, and first-run catalog builds (a tiny fixture plus
one test that builds the real JSONL). They never hit the network and they
do not commit or require a SQLite file in the repo. They are **not** a live
Hermes Desktop proof — the pane still needs a real host before a catalog
submission.

Schema tokens are measured with tiktoken `o200k_base` (and `cl100k_base` for
comparison). Keep the two `op`-style tools; do not split them into many
fine-grained tools, and do not add a model-callable download tool.

Bump the version in one place with
`python scripts/bump_plugin_version.py 0.2.0` (also updates `pyproject.toml`
and `assetrizz_plugin/__init__.py`). Tag, release, catalog submit, and deploy
only with an explicit yes from the owner.
