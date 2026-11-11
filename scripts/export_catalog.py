#!/usr/bin/env python3
"""Export a scannable assets.jsonl from a library SQLite database."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

# Keep this list in step with assetrizz_plugin.catalog.CATALOG_FIELDS.
FIELDS = [
    "id",
    "slug",
    "path",
    "thumb_path",
    "category",
    "subcategory",
    "subject",
    "style_pack",
    "tags",
    "description",
    "width",
    "height",
    "has_alpha",
    "tileable",
    "status",
    "palette",
    "dominant_colors",
    "pivot",
    "frame_info",
    "license",
    "sha256",
    "qa_notes",
]
JSON_FIELDS = {"tags", "palette", "dominant_colors", "pivot", "frame_info", "qa_notes"}


def export_jsonl(db_path: Path, dest: Path) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    present = {row[1] for row in conn.execute("PRAGMA table_info(assets)")}
    missing = [name for name in FIELDS if name not in present]
    if missing:
        raise SystemExit(f"assets table is missing columns: {', '.join(missing)}")
    rows = conn.execute(
        f"SELECT {', '.join(FIELDS)} FROM assets ORDER BY id ASC"
    ).fetchall()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".partial")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            obj = {}
            for key in FIELDS:
                value = row[key]
                if value is None:
                    continue
                if key in JSON_FIELDS and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                obj[key] = value
            handle.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    dest.with_name(dest.name + ".sha256").write_text(
        f"{digest}  {dest.name}\n", encoding="utf-8"
    )
    print(f"{len(rows)} rows -> {dest} ({dest.stat().st_size} bytes)")
    print(digest)
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="Path to assets.db (uncompressed)")
    parser.add_argument("output", type=Path, help="Path to write assets.jsonl")
    args = parser.parse_args()
    if not args.database.is_file():
        print(f"no database at {args.database}", file=sys.stderr)
        return 2
    export_jsonl(args.database, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
