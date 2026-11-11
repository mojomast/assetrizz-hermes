"""Build a lean SQLite+FTS catalog from the scannable JSONL source.

The plugin repo ships db/assets.jsonl (plain UTF-8, one asset per line) so
catalog reviewers can read every record. SQLite is created on first use in
the plugin data directory, never committed. A complete mojomast/assetrizz
library checkout may still have db/assets.db or db/assets.db.xz; those
paths are handled in library.restore_db and are not bundled here.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator

from assetrizz_plugin import BUNDLED_CATALOG_SHA256
from assetrizz_plugin.errors import LibraryError
from assetrizz_plugin.paths import refuse_denied_write, require_non_root

CATALOG_FIELDS = (
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
)
JSON_FIELDS = frozenset(
    {"tags", "palette", "dominant_colors", "pivot", "frame_info", "qa_notes"}
)
INT_FIELDS = frozenset({"id", "width", "height", "has_alpha", "tileable"})
_REQUIRED = frozenset({"id", "slug", "path", "status"})
_SOURCE_NAME = "assets.jsonl"
_STAMP_SUFFIX = ".source-sha256"
_SCHEMA_VERSION = "1"

_ASSETS_DDL = """
CREATE TABLE assets (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  path TEXT NOT NULL,
  thumb_path TEXT,
  category TEXT,
  subcategory TEXT,
  subject TEXT,
  style_pack TEXT,
  tags TEXT,
  description TEXT,
  width INTEGER,
  height INTEGER,
  has_alpha INTEGER,
  palette TEXT,
  dominant_colors TEXT,
  tileable INTEGER DEFAULT 0,
  pivot TEXT,
  frame_info TEXT,
  license TEXT,
  sha256 TEXT,
  status TEXT NOT NULL DEFAULT 'ok',
  qa_notes TEXT
);
CREATE UNIQUE INDEX idx_assets_sha256 ON assets(sha256) WHERE sha256 IS NOT NULL;
CREATE INDEX idx_assets_cat ON assets(category, style_pack, status);
CREATE INDEX idx_assets_subject ON assets(subject);
CREATE INDEX idx_assets_alpha ON assets(has_alpha, tileable, width, height);
CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""

_FTS_DDL = """
CREATE VIRTUAL TABLE assets_fts USING fts5(
  slug,
  description,
  tags,
  subject,
  category,
  subcategory,
  style_pack,
  content='assets',
  content_rowid='id'
);
CREATE TRIGGER assets_ai AFTER INSERT ON assets BEGIN
  INSERT INTO assets_fts(rowid, slug, description, tags, subject, category, subcategory, style_pack)
  VALUES (new.id, new.slug, new.description, new.tags, new.subject, new.category, new.subcategory, new.style_pack);
END;
CREATE TRIGGER assets_ad AFTER DELETE ON assets BEGIN
  INSERT INTO assets_fts(assets_fts, rowid, slug, description, tags, subject, category, subcategory, style_pack)
  VALUES ('delete', old.id, old.slug, old.description, old.tags, old.subject, old.category, old.subcategory, old.style_pack);
END;
CREATE TRIGGER assets_au AFTER UPDATE ON assets BEGIN
  INSERT INTO assets_fts(assets_fts, rowid, slug, description, tags, subject, category, subcategory, style_pack)
  VALUES ('delete', old.id, old.slug, old.description, old.tags, old.subject, old.category, old.subcategory, old.style_pack);
  INSERT INTO assets_fts(rowid, slug, description, tags, subject, category, subcategory, style_pack)
  VALUES (new.id, new.slug, new.description, new.tags, new.subject, new.category, new.subcategory, new.style_pack);
END;
"""


def plugin_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundled_catalog_source() -> Path:
    return plugin_root() / "db" / _SOURCE_NAME


def catalog_stamp_path(dest: Path) -> Path:
    return dest.with_name(dest.name + _STAMP_SUFFIX)


def iter_catalog_rows(source: Path) -> Iterator[dict[str, Any]]:
    """Yield one asset dict per JSONL line. Raises LibraryError on bad input."""
    try:
        handle = source.open("r", encoding="utf-8")
    except OSError as exc:
        raise LibraryError(
            f"Cannot read catalog source at {source}.",
            code="library_missing",
            fix="Reinstall the plugin so db/assets.jsonl is present.",
        ) from exc
    with handle:
        for lineno, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LibraryError(
                    f"Catalog source {source.name} is not valid JSON on line {lineno}.",
                    code="library_missing",
                    fix="Reinstall the plugin so db/assets.jsonl is the pinned snapshot.",
                ) from exc
            if not isinstance(row, dict):
                raise LibraryError(
                    f"Catalog source {source.name} line {lineno} is not a JSON object.",
                    code="library_missing",
                    fix="Reinstall the plugin so db/assets.jsonl is the pinned snapshot.",
                )
            missing = _REQUIRED - set(row)
            if missing:
                raise LibraryError(
                    f"Catalog source {source.name} line {lineno} is missing {sorted(missing)}.",
                    code="library_missing",
                    fix="Reinstall the plugin so db/assets.jsonl is the pinned snapshot.",
                )
            yield row


def _sql_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in JSON_FIELDS:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if key in INT_FIELDS:
        return int(value)
    return value


def _insert_row(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    values = []
    keys = []
    for key in CATALOG_FIELDS:
        if key not in row:
            continue
        keys.append(key)
        values.append(_sql_value(key, row[key]))
    conn.execute(
        f"INSERT INTO assets ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
        values,
    )


def _read_stamp(dest: Path) -> str | None:
    stamp = catalog_stamp_path(dest)
    if not stamp.is_file():
        return None
    try:
        return stamp.read_text(encoding="utf-8").split()[0].strip().lower()
    except OSError:
        return None


def _write_stamp(dest: Path, digest: str) -> None:
    stamp = catalog_stamp_path(dest)
    tmp = stamp.with_name(stamp.name + ".partial")
    tmp.write_text(f"{digest}  {dest.name}\n", encoding="utf-8")
    os.replace(tmp, stamp)


def catalog_is_current(dest: Path, expected_sha256: str) -> bool:
    """True when dest is a usable catalog built from the expected source digest."""
    if not dest.is_file():
        return False
    want = expected_sha256.strip().lower()
    if _read_stamp(dest) != want:
        return False
    try:
        conn = sqlite3.connect(f"file:{dest}?mode=ro", uri=True)
        try:
            conn.execute("SELECT 1 FROM assets LIMIT 1").fetchone()
            conn.execute("SELECT 1 FROM assets_fts LIMIT 1").fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return True


def _lock_file(path: Path):
    """Exclusive file lock with a portable fallback when fcntl is missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        return handle
    except ImportError:
        pass
    try:
        import msvcrt

        handle.seek(0)
        if handle.read(1) == b"":
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
    except ImportError:
        pass
    return handle


def _unlock_file(handle) -> None:
    if handle is None:
        return
    try:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except ImportError:
        try:
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except (ImportError, OSError):
            pass
    except OSError:
        pass
    try:
        handle.close()
    except OSError:
        pass


def _populate(conn: sqlite3.Connection, source: Path, digest: str) -> int:
    conn.executescript(_ASSETS_DDL)
    count = 0
    conn.execute("BEGIN")
    try:
        for row in iter_catalog_rows(source):
            _insert_row(conn, row)
            count += 1
        conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            ("catalog_schema", _SCHEMA_VERSION),
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            ("source_sha256", digest),
        )
        conn.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            ("source_name", source.name),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    # Build FTS after the bulk insert so triggers do not fire per row.
    conn.executescript(_FTS_DDL)
    conn.execute("INSERT INTO assets_fts(assets_fts) VALUES ('rebuild')")
    conn.commit()
    return count


def build_catalog_from_jsonl(
    source: Path,
    dest: Path,
    expected_sha256: str,
) -> Path:
    """Build dest from a pinned JSONL source. Rebuilds when the source hash changes.

    Never writes into the source tree. An existing dest without a matching
    stamp (for example a leftover decompressed v0.1.0 snapshot) is replaced.
    """
    from assetrizz_plugin.library import verify_file_sha256

    source = require_non_root(Path(source), label="catalog source")
    dest = Path(dest).expanduser()
    digest = verify_file_sha256(
        source, expected_sha256, label="bundled catalog source"
    )
    if catalog_is_current(dest, digest):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    refuse_denied_write(dest, label="catalog db")
    lock_path = dest.with_name(dest.name + ".lock")
    handle = None
    try:
        handle = _lock_file(lock_path)
        # Another process may have finished while we waited.
        if catalog_is_current(dest, digest):
            return dest
        tmp = dest.with_name(dest.name + ".partial")
        if tmp.exists():
            tmp.unlink()
        conn = sqlite3.connect(os.fspath(tmp))
        try:
            conn.execute("PRAGMA journal_mode = OFF")
            conn.execute("PRAGMA synchronous = OFF")
            conn.execute("PRAGMA temp_store = MEMORY")
            _populate(conn, source, digest)
            conn.execute("PRAGMA synchronous = NORMAL")
        finally:
            conn.close()
        os.replace(tmp, dest)
        _write_stamp(dest, digest)
        return dest
    except Exception:
        tmp = dest.with_name(dest.name + ".partial")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    finally:
        _unlock_file(handle)
        try:
            if lock_path.exists():
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def restore_bundled_catalog(dest: Path | None = None) -> Path:
    from assetrizz_plugin.paths import data_home

    if dest is None:
        dest = data_home() / "catalog" / "assets.db"
    source = bundled_catalog_source()
    if not source.is_file():
        raise LibraryError(
            f"No scannable catalog source at {source}.",
            code="library_missing",
            fix="Reinstall the plugin so db/assets.jsonl is present, or point Library path at a library checkout.",
        )
    return build_catalog_from_jsonl(source, dest, BUNDLED_CATALOG_SHA256)


def build_elapsed_ms(source: Path, dest: Path, expected_sha256: str) -> tuple[Path, float]:
    """Build (or reuse) a catalog and return (path, milliseconds)."""
    start = time.perf_counter()
    path = build_catalog_from_jsonl(source, dest, expected_sha256)
    return path, (time.perf_counter() - start) * 1000
