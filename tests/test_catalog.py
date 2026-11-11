"""First-run catalog build from scannable JSONL, and repo hygiene."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from assetrizz_plugin import BUNDLED_CATALOG_SHA256
from assetrizz_plugin.catalog import (
    CATALOG_FIELDS,
    build_catalog_from_jsonl,
    bundled_catalog_source,
    catalog_is_current,
    catalog_stamp_path,
    iter_catalog_rows,
)
from assetrizz_plugin.errors import LibraryError
from assetrizz_plugin.library import reset_cache, restore_db, search, stats

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {
    ".xz",
    ".gz",
    ".bz2",
    ".zip",
    ".7z",
    ".zst",
    ".lz4",
    ".lzma",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".bin",
    ".wasm",
    ".so",
    ".dylib",
    ".whl",
}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".eggs", "dist", "build", ".venv", "venv"}


def _write_jsonl(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def _mini_rows() -> list[dict]:
    return [
        {
            "id": 1,
            "slug": "pixel_32/tiles/floor/grass_base",
            "path": "assets/pixel_32/tiles/floor/grass_base.png",
            "category": "tiles",
            "subcategory": "floor",
            "subject": "grass",
            "style_pack": "pixel_32",
            "tags": ["tiles", "floor", "grass", "tileable"],
            "description": "A grass floor tile, tileable.",
            "width": 16,
            "height": 16,
            "has_alpha": 1,
            "tileable": 1,
            "status": "ok",
            "license": "original, generated for Kyle Durepos",
            "sha256": "a" * 64,
        },
        {
            "id": 2,
            "slug": "pixel_32/props/object/crate_plain",
            "path": "assets/pixel_32/props/object/crate_plain.png",
            "category": "props",
            "subject": "crate",
            "style_pack": "pixel_32",
            "tags": ["props", "crate"],
            "description": "A plain wooden crate.",
            "width": 24,
            "height": 24,
            "has_alpha": 1,
            "tileable": 0,
            "status": "ok",
            "sha256": "b" * 64,
        },
        {
            "id": 3,
            "slug": "pixel_32/props/object/broken_vase",
            "path": "assets/pixel_32/props/object/broken_vase.png",
            "category": "props",
            "subject": "vase",
            "style_pack": "pixel_32",
            "description": "Rejected vase.",
            "width": 16,
            "height": 16,
            "status": "rejected",
            "sha256": "c" * 64,
        },
    ]


def test_repo_has_no_compressed_or_sqlite_catalog_blobs():
    found = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in FORBIDDEN_SUFFIXES:
            found.append(path.relative_to(ROOT).as_posix())
    assert found == [], f"compressed or binary catalog blobs in the repo: {found}"
    source = ROOT / "db" / "assets.jsonl"
    assert source.is_file()
    # First line must be a UTF-8 JSON object the scanner can read.
    first = source.read_text(encoding="utf-8").splitlines()[0]
    row = json.loads(first)
    assert isinstance(row, dict) and "slug" in row and "sha256" in row
    for key in row:
        assert key in CATALOG_FIELDS


def test_bundled_pin_constant_matches_sidecar_and_file():
    source = bundled_catalog_source()
    sidecar = source.with_name(source.name + ".sha256")
    text = sidecar.read_text(encoding="utf-8").split()[0].strip().lower()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert text == BUNDLED_CATALOG_SHA256 == digest


def test_build_from_jsonl_and_reuse(tmp_path):
    source = tmp_path / "assets.jsonl"
    digest = _write_jsonl(source, _mini_rows())
    dest = tmp_path / "catalog" / "assets.db"
    built = build_catalog_from_jsonl(source, dest, digest)
    assert built == dest
    assert dest.is_file()
    assert catalog_is_current(dest, digest)
    conn = sqlite3.connect(dest)
    conn.row_factory = sqlite3.Row
    try:
        counts = dict(conn.execute("SELECT status, COUNT(*) n FROM assets GROUP BY status"))
        assert counts == {"ok": 2, "rejected": 1}
        tags = json.loads(conn.execute("SELECT tags FROM assets WHERE id=1").fetchone()["tags"])
        assert "tileable" in tags
        hits = conn.execute(
            "SELECT a.slug FROM assets a JOIN assets_fts ON assets_fts.rowid = a.id "
            "WHERE assets_fts MATCH ? AND a.status='ok'",
            ("grass",),
        ).fetchall()
        assert [row["slug"] for row in hits] == ["pixel_32/tiles/floor/grass_base"]
    finally:
        conn.close()
    stamp = dest.stat().st_mtime_ns
    again = build_catalog_from_jsonl(source, dest, digest)
    assert again == dest
    assert dest.stat().st_mtime_ns == stamp


def test_build_rejects_bad_pin_and_leaves_no_dest(tmp_path):
    source = tmp_path / "assets.jsonl"
    _write_jsonl(source, _mini_rows())
    dest = tmp_path / "catalog" / "assets.db"
    with pytest.raises(LibraryError) as exc:
        build_catalog_from_jsonl(source, dest, "0" * 64)
    assert exc.value.code == "hash_mismatch"
    assert not dest.exists()
    assert not dest.with_name(dest.name + ".partial").exists()


def test_rebuilds_when_stamp_missing_or_source_changes(tmp_path):
    source = tmp_path / "assets.jsonl"
    digest = _write_jsonl(source, _mini_rows())
    dest = tmp_path / "catalog" / "assets.db"
    build_catalog_from_jsonl(source, dest, digest)
    catalog_stamp_path(dest).unlink()
    # Leftover unstamped db (the v0.1.0 decompressed snapshot case) is rebuilt.
    dest.write_bytes(b"not-a-usable-catalog")
    rebuilt = build_catalog_from_jsonl(source, dest, digest)
    assert rebuilt == dest
    assert catalog_is_current(dest, digest)

    rows = _mini_rows()
    rows[0]["description"] = "Updated grass tile."
    new_digest = _write_jsonl(source, rows)
    assert new_digest != digest
    build_catalog_from_jsonl(source, dest, new_digest)
    conn = sqlite3.connect(dest)
    try:
        text = conn.execute("SELECT description FROM assets WHERE id=1").fetchone()[0]
        assert text == "Updated grass tile."
    finally:
        conn.close()
    assert catalog_is_current(dest, new_digest)
    assert not catalog_is_current(dest, digest)


def test_iter_catalog_rows_rejects_bad_lines(tmp_path):
    source = tmp_path / "assets.jsonl"
    source.write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(LibraryError) as exc:
        list(iter_catalog_rows(source))
    assert exc.value.code == "library_missing"
    source.write_text(json.dumps({"slug": "no-id"}) + "\n", encoding="utf-8")
    with pytest.raises(LibraryError):
        list(iter_catalog_rows(source))


def test_restore_db_builds_from_jsonl(tmp_path):
    library = tmp_path / "lib"
    (library / "assets").mkdir(parents=True)
    digest = _write_jsonl(library / "db" / "assets.jsonl", _mini_rows())
    fallback = tmp_path / "data" / "assets.db"
    restored = restore_db(library, fallback)
    assert restored == library / "db" / "assets.db"
    assert restored.is_file()
    assert catalog_is_current(restored, digest)
    # Second call leaves the built db alone.
    stamp = restored.stat().st_mtime_ns
    again = restore_db(library, fallback)
    assert again == restored
    assert again.stat().st_mtime_ns == stamp


def test_first_run_bundled_catalog_builds_and_searches(tmp_path, monkeypatch):
    """Build the real bundled JSONL and search it. This is the first-run path."""
    monkeypatch.setenv("ASSETRIZZ_LIBRARY", "none")
    monkeypatch.setenv("ASSETRIZZ_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("ASSETRIZZ_LOCAL_LIBRARY", raising=False)
    reset_cache()
    source = bundled_catalog_source()
    dest = tmp_path / "data" / "catalog" / "assets.db"
    built = build_catalog_from_jsonl(source, dest, BUNDLED_CATALOG_SHA256)
    assert built == dest
    # Point the plugin at the db we just built by using the data-home catalog path
    # through restore_bundled_catalog / current_db.
    from assetrizz_plugin.catalog import restore_bundled_catalog

    reset_cache()
    path = restore_bundled_catalog()
    assert path == dest
    info = stats()
    assert info["total_ok"] == 14641
    assert info["total_rejected"] == 132
    assert info["catalog"] == "bundled"
    grass = search("grass_base", style="pixel_32", category="tiles", limit=5)
    assert grass["ok"] is True
    assert grass["total"] >= 1
    slugs = {item["slug"] for item in grass["items"]}
    assert "pixel_32/tiles/floor/grass_base" in slugs
    reset_cache()
