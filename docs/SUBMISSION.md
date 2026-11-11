# Catalog submission — assetrizz v0.2.0

**Status: v0.2.0 is tagged on main. A YAML-only catalog branch can be pushed
on the mojomast/hermes-agent fork, but [NousResearch/hermes-agent#152771](https://github.com/NousResearch/hermes-agent/pull/152771)
must not be updated until Kyle explicitly says yes.** compose-v2 is a minor
feature on top of the 0.1.1 scannable-catalog fix.

- Plugin repo: https://github.com/mojomast/assetrizz-hermes
- Version: `0.2.0`
- Library asset pin (unchanged): [mojomast/assetrizz](https://github.com/mojomast/assetrizz) tag `v0.1.0`, commit `05339c228f55ac95ad21b5c947db0c6e36207cd4`
- Catalog PR to repin later: https://github.com/NousResearch/hermes-agent/pull/152771
- Existing PR head branch (do not push to it): `catalog/assetrizz-hermes-v0.1.0`
- New fork branch for the v0.2.0 pin: `catalog/assetrizz-hermes-v0.2.0`

## What changed since 0.1.1

- `assetrizz_scene` `op=compose`, four gameplay templates, layer lint, and canvas HUD/playfield guides.
- Schema tokens: **970** (`o200k_base`; was 931, +39, cap +80).
- Versions in `plugin.yaml`, `pyproject.toml`, `dashboard/manifest.json`, and the README all read `0.2.0`.
- CHANGELOG added. Catalog bars from 0.1.1 still hold: scannable JSONL (no compressed catalog blob), Hermes SSRF guard on pinned GitHub raw fetches, `ctx.rest` pane, `requires_hermes: ">=0.23.0"`, no credentials, path confinement, `get_hermes_home()` / `plugin_data_dir` for data paths.

The pin SHA belongs on the `v0.2.0` tag, not on a later docs-only follow-up.

The v0.1.1 notes below are historical.

---

# Catalog submission — assetrizz v0.1.1

**Status: v0.1.1 is the review fix for [NousResearch/hermes-agent#152771](https://github.com/NousResearch/hermes-agent/pull/152771).**
teknium1 requested changes on 10 Nov 2026 (9:46 PM America/Toronto) because
`db/assets.db.xz` was compressed and the catalog scanner could not read
inside it. This release removes that snapshot and ships a scannable
`db/assets.jsonl` instead. The plugin builds a lean SQLite + FTS5 catalog
in the plugin data directory on first run.

- Plugin repo: https://github.com/mojomast/assetrizz-hermes
- Version: `0.1.1` (tag / release once this lands on main)
- Library asset pin (unchanged): [mojomast/assetrizz](https://github.com/mojomast/assetrizz) tag `v0.1.0`, commit `05339c228f55ac95ad21b5c947db0c6e36207cd4`
- Catalog PR to repin: https://github.com/NousResearch/hermes-agent/pull/152771
- Fork branch: `catalog/assetrizz-hermes-v0.1.0` (same branch; bump `sha` / `version` after the tag exists)

## Why JSONL, not an uncompressed `.db`

The decompressed v0.1.0 SQLite file is **147 MB**. Most of that is generation
pipeline data this plugin never queries (`specs` ~69 MB, asset prompts,
`batches`, claims). Even a lean `.db` would still be a binary the scanner
cannot read as source. The JSONL is **14.98 MiB** of UTF-8, one asset per
line, and contains only the fields search and compose use (14,773 rows:
14,641 `ok`, 132 `rejected`). It is pinned by `db/assets.jsonl.sha256` and
`BUNDLED_CATALOG_SHA256`. First-run build of the lean index takes about
**0.55 s** and produces an 18 MB SQLite file under the plugin data dir,
never in the checkout. A leftover decompressed v0.1.0 db without a source
stamp is rebuilt. Local / on_demand / offline modes still work. A complete
mojomast/assetrizz checkout that still has `db/assets.db` or
`db/assets.db.xz` is accepted.

## Checks on this tree (America/Toronto, 11 Nov 2026)

- Pytest: **47 passed** (the previous 40 plus first-run build, pin, rebuild,
  and “no compressed or SQLite catalog blobs in the repo” tests).
- Schema cost unchanged: **2 tools, 931 tokens** (`o200k_base`; 918 on
  `cl100k_base`).
- `hermes plugins doctor . --ci`: 2 tool(s), 0 hook(s).
- `hermes plugins validate . --install-deps`: passed; security scan **safe**.
  Same documented-seam warning as v0.1.0 (`create_ssrf_safe_client`,
  `get_write_denied_error`).
- Work tree (excluding `.git`): **16 MB**, of which 15 MB is `db/assets.jsonl`.
  No `.xz` / `.gz` / `.zip` / `.db` catalog blobs remain in the plugin tree.
  `docs/banner.jpg` and `docs/example-scene.png` are the existing reviewable
  docs images.
- Secret-scan: `detect-secrets` and a credential-pattern pass; no secrets.
  The only hex-entropy hits were the public catalog SHA-256 pin and
  already-public commit SHAs in this file.
- Assets stay pinned to mojomast/assetrizz `v0.1.0` (`05339c2`).

The v0.1.0 notes below are historical.

---

# Historical notes — assetrizz v0.1.0

**Status: ready to open, waiting for Kyle's yes.** The plugin lives in
`mojomast/assetrizz-hermes`. The v0.1.0 tag and GitHub release exist. The
catalog branch is on the fork. The catalog PR on `NousResearch/hermes-agent`
has **not** been opened.

- Plugin repo: https://github.com/mojomast/assetrizz-hermes
- Merge / **catalog pin:** `023e61cb604343a9e74836ad471ae25439dda745`
- Tag / release: https://github.com/mojomast/assetrizz-hermes/releases/tag/v0.1.0
- Library asset pin (unchanged): [mojomast/assetrizz](https://github.com/mojomast/assetrizz) tag `v0.1.0`, commit `05339c228f55ac95ad21b5c947db0c6e36207cd4`
- Fork branch: https://github.com/mojomast/hermes-agent/tree/catalog/assetrizz-hermes-v0.1.0
  (commit `186a0e6b10c942a7bd5bad2bba71f0a9f04984c6`, YAML-only, off upstream
  `main` at `ec3249919accf7bc51f780dcff663e8f19a0e176`)
- Compare (open this after Kyle's yes; do not open the PR yet):
  https://github.com/NousResearch/hermes-agent/compare/main...mojomast:hermes-agent:catalog/assetrizz-hermes-v0.1.0?expand=1
- This file was added *after* the tag so it could carry the real sha. The pin
  still points at the tagged commit, not at this docs follow-up.
- Open mojomast catalog PRs on `NousResearch/hermes-agent`: **4 of 5**
  (#152699 Hermes Plugin Dev, #151946 stitchslop, #150358 Hermagotchi,
  #149691 Eye Of Hermes). Opening this listing now would be the fifth open
  PR. Wait until one lands or closes, and until Kyle says yes.

## Already done

- Created public repo https://github.com/mojomast/assetrizz-hermes with
  history of `plugin/` preserved from mojomast/assetrizz via `git subtree
  split` (two parent commits) plus a follow-up that added tests, docs, and
  the standalone README.
- Tagged `v0.1.0` on `023e61cb604343a9e74836ad471ae25439dda745` and
  published the GitHub release at 11:16 AM America/Toronto on 10 Nov 2026
  (approximate; tag push shortly after the repo was created).
- Banner at the pin returns HTTP 200:
  https://raw.githubusercontent.com/mojomast/assetrizz-hermes/023e61cb604343a9e74836ad471ae25439dda745/docs/banner.jpg
  (1280×720). Asset raw URLs remain on the library tag (also HTTP 200), e.g.
  `https://raw.githubusercontent.com/mojomast/assetrizz/v0.1.0/assets/pixel_32/tiles/floor/grass_base.png`.
- Tools: `assetrizz_search`, `assetrizz_scene`. Hooks: none. Env: none.
  Bulk library download is **not** a tool; it is a pane button and
  `python -m assetrizz_plugin.cli` only.
- Schema cost: **2 tools, 931 tokens** (tiktoken `o200k_base`; 918 on
  `cl100k_base`).
- `hpd_check` was green. `hermes plugins doctor . --ci` and
  `hermes plugins validate . --install-deps` were green on the release
  tree. Security scan: **safe**. Requires Hermes `>=0.23.0`. Local CLI used
  for those checks: Hermes Agent v0.23.0 (`2bd378ed1b8d`). Validate warned
  that `tools.url_safety.create_ssrf_safe_client` and
  `agent.file_safety.get_write_denied_error` are documented seams but not
  formal plugin APIs; the SSRF guard is required for on-demand fetches, and
  a stdlib fallback exists. Pytest: **40 passed**, all fetches mocked.
- Installed plugin size (this repo, including the 4.7 MB catalog snapshot,
  banner, and example scene): **5.54 MB**. A full local library download is
  about **1.65 GB**.
- `scripts/validate_plugin_catalog.py plugin-catalog/assetrizz.yaml` on the
  fork branch: **OK: 1 file(s) valid**.
- Scratch-home install (`HERMES_HOME` throwaway, not the live profile):
  `hermes plugins install mojomast/assetrizz-hermes --ref 023e61cb604343a9e74836ad471ae25439dda745 --enable --yes-deps`
  finished in **20.81 s** (including isolated-runtime bootstrap on a fresh
  home), landed at `$HERMES_HOME/plugins/assetrizz` with `plugin.yaml` at the
  repo root, no `assets/` tree, one PNG (`docs/example-scene.png` only),
  `pinned=True`, `revision=023e61cb604343a9e74836ad471ae25439dda745`, work
  tree **5.54 MB**, bundled `db/assets.db.xz` SHA-256 matched the pin, the
  plugin was enabled, and `hermes plugins doctor assetrizz --ci` reported
  **2 tool(s), 0 hook(s)** at version 0.1.0. The scratch home was then
  deleted.
- Catalog CI no longer has to clone the 1.65 GB library repo; the plugin
  repo is 5.54 MB, so the previous full-clone / 600 s known issue was
  removed from the catalog entry.
- The in-tree `plugin/` in mojomast/assetrizz was **not** deleted. A README
  pointer and a superseded note were added on that repo’s main
  (`79c63c8`).
- No extra screenshots (under the 6-shot cap). The example scene is
  `docs/example-scene.png`.

## Still needs Kyle's yes

Open a YAML-only PR from the fork branch to `NousResearch/hermes-agent`,
adding only `plugin-catalog/assetrizz.yaml`. Use the title and body
below. Do not open it while 4 of 5 catalog PRs are already open, and do
not comment on other catalog threads unless asked.

## Catalog entry (already on the fork branch)

The file at
https://github.com/mojomast/hermes-agent/blob/catalog/assetrizz-hermes-v0.1.0/plugin-catalog/assetrizz.yaml
is:

```yaml
name: assetrizz
title: Assetrizz
repo: https://github.com/mojomast/assetrizz-hermes
sha: "023e61cb604343a9e74836ad471ae25439dda745"
subdir: ""
description: >-
  Skill id assetrizz:assetrizz-composer. Search the assetrizz 2D game-asset
  catalog (FTS over slugs, tags, descriptions, styles, and categories) and
  compose scenes from those assets. Tools: assetrizz_search and assetrizz_scene.
  This plugin repo is about 5.1 MB including a 4.7 MB SHA-256-pinned catalog,
  so search works after install. The 14,641 PNGs (about 1.65 GB, 23 style
  packs) live in https://github.com/mojomast/assetrizz and are not copied
  into the plugins folder. Asset mode is one of on_demand (default: fetch a
  single PNG from GitHub raw when you place, render, or preview it), local
  (you download the full library or chosen style packs once into a directory
  you pick), or offline (local files only, no network). Bulk library
  downloads are user-initiated only — use the Download library button in the
  Desktop pane (size estimate, progress, cancel) or
  python -m assetrizz_plugin.cli; they are not a model tool. Fetches go only
  to raw.githubusercontent.com/mojomast/assetrizz/v0.1.0/assets/… (library
  tag v0.1.0, commit 05339c228f55ac95ad21b5c947db0c6e36207cd4), use the
  Hermes SSRF guard, cap size, and verify SHA-256 from the catalog. Optional
  library_path still prefers a complete library checkout when you have one.
  Rendered scenes write PNG and JSON under the plugin data directory and, if
  you set it, the Export directory (must not be a filesystem root; never
  chosen by a tool argument). No credentials, no subprocesses. Hermes
  Desktop 0.23 or newer can show a dark compose pane that live-previews the
  current scene through ctx.rest and lets you install or remove a local
  library (deletion needs confirmation). The two tools still run when that
  pane is unavailable.
maintainer: mojomast
tier: community
category: tools
requires_hermes: ">=0.23.0"
docs_url: https://github.com/mojomast/assetrizz-hermes#readme
version: "0.1.0"
image: https://raw.githubusercontent.com/mojomast/assetrizz-hermes/023e61cb604343a9e74836ad471ae25439dda745/docs/banner.jpg
readme: true
platforms: []
known_issues:
  - >-
    The Desktop compose pane has not yet been proven on a live Hermes
    Desktop host; the two tools and the mocked pane API tests still run
    without it.
capabilities:
  provides_tools:
    - assetrizz_search
    - assetrizz_scene
  provides_hooks: []
  provides_middleware: []
  requires_env: []
```

## Draft PR title

`plugin-catalog: add assetrizz v0.1.0`

## Draft PR body

```markdown
## plugin-catalog: add assetrizz v0.1.0

Adds `plugin-catalog/assetrizz.yaml` (YAML-only diff).

- **Repo:** https://github.com/mojomast/assetrizz-hermes
- **Pinned SHA:** `023e61cb604343a9e74836ad471ae25439dda745` (tag `v0.1.0`, release: https://github.com/mojomast/assetrizz-hermes/releases/tag/v0.1.0)
- **Subdir:** none (repo root)
- **Maintainer:** @mojomast (owner of the plugin repo)
- **Library assets:** PNGs stay in https://github.com/mojomast/assetrizz and are fetched from tag `v0.1.0` (commit `05339c228f55ac95ad21b5c947db0c6e36207cd4`), SHA-256 verified against the bundled catalog.

### What it does

Two tools plus a dark Desktop compose pane for a 14,641-PNG 2D game-asset
library. Search uses a bundled, SHA-256-pinned catalog (~4.7 MB) so a catalog
install is about 5.5 MB and does not clone the 1.65 GB library. Default
`on_demand` mode fetches a single PNG from the library tag when it is placed,
rendered, or previewed (Hermes SSRF guard, size cap, SHA-256 verified into
the plugin cache). `local` lets the user download the full library or chosen
style packs once; `offline` never touches the network. Bulk downloads are
user-initiated only (pane button or `python -m assetrizz_plugin.cli`), not a
model tool.

### Checks run before this PR

- `hpd_check` green; `hermes plugins doctor --ci` and
  `hermes plugins validate --install-deps` green (security scan: safe).
- Pytest 40 passed with mocked fetches (no live network in CI).
- Schema cost: 931 tokens (`o200k_base`), 2 tools, 0 hooks, no env.
- Scratch-home install of `mojomast/assetrizz-hermes` at this SHA: 20.81 s,
  5.54 MB work tree, no PNG library copied, doctor reported 2 tools / 0 hooks.
- `scripts/validate_plugin_catalog.py` on this file: OK.

### Known issue for reviewers

The Desktop pane has not yet been proven on a live Hermes Desktop host. The
two tools and mocked pane API tests still run without it.
```
