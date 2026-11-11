# Bundled catalog source

`assets.jsonl` is the scannable, plain-text source for the plugin catalog.
The catalog scanner can read every record as it sits in the repo. There is
no compressed or SQLite database in this tree.

Each line is one JSON object (UTF-8, no pretty-print). Fields are the ones
`assetrizz_search` / `assetrizz_scene` actually use: identity (`id`, `slug`,
`path`, `sha256`, `status`), classification (`category`, `subcategory`,
`subject`, `style_pack`, `tags`, `description`), raster hints (`width`,
`height`, `has_alpha`, `tileable`, `palette`, `dominant_colors`, `pivot`,
`frame_info`, `thumb_path`), plus `license` and `qa_notes`.

The full `mojomast/assetrizz` v0.1.0 SQLite snapshot is about 147 MB,
mostly generation-pipeline tables (`specs`, `batches`, prompts) that this
plugin never queries. Those stay in the library repo. This file holds
14,773 rows (14,641 `ok`, 132 `rejected`) and is SHA-256 pinned by
`assets.jsonl.sha256` and `BUNDLED_CATALOG_SHA256`.

On first search (or a user-initiated library download) the plugin builds a
lean SQLite + FTS5 database in the plugin data directory, never in this
checkout. A later plugin update with a new JSONL hash rebuilds that copy.
An existing `assets.db` or `assets.db.xz` in a complete library checkout
is still accepted.

To regenerate this file from a library checkout:

```bash
python scripts/export_catalog.py /path/to/assetrizz/db/assets.db db/assets.jsonl
```

PNGs remain pinned to `mojomast/assetrizz` tag `v0.1.0`
(`05339c228f55ac95ad21b5c947db0c6e36207cd4`).
