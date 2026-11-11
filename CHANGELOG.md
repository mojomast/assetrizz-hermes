# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-11

Minor feature release: compose-v2.

### Added

- `assetrizz_scene` `op=compose` compiles a compact signed scene spec into a placed scene.
- Four gameplay templates: `topdown_farming`, `topdown_shooter`, `dungeon_crawler`, and `side_platformer`.
- Layer lint for collisions, HUD/playfield overlap, off-canvas placement, and related layout issues, so a spec can be revised instead of placed blindly.
- Canvas HUD / playfield guides in the Desktop compose pane (`ctx.rest`).

### Changed

- Combined tool-schema cost is **970** tokens on `o200k_base` (was 931; +39, within the +80 cap).
- Plugin, package, and dashboard manifest versions are `0.2.0`.

The bundled catalog is still the scannable `db/assets.jsonl` introduced in 0.1.1. Library PNGs stay pinned to [mojomast/assetrizz](https://github.com/mojomast/assetrizz) tag `v0.1.0` (`05339c228f55ac95ad21b5c947db0c6e36207cd4`).

## [0.1.1] - 2026-11-11

Review fix for the catalog listing ([NousResearch/hermes-agent#152771](https://github.com/NousResearch/hermes-agent/pull/152771)).

### Changed

- Replaced the unscannable `db/assets.db.xz` snapshot with a UTF-8 `db/assets.jsonl` catalog (14,773 rows; only the fields search and compose use).
- The plugin builds a lean SQLite + FTS5 index in the plugin data directory on first search.

## [0.1.0] - 2026-11-10

Initial public plugin release: search, scene tools, on_demand / local / offline asset modes, and a Desktop compose pane.

[0.2.0]: https://github.com/mojomast/assetrizz-hermes/releases/tag/v0.2.0
[0.1.1]: https://github.com/mojomast/assetrizz-hermes/releases/tag/v0.1.1
[0.1.0]: https://github.com/mojomast/assetrizz-hermes/releases/tag/v0.1.0
