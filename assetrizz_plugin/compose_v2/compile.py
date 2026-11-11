"""Compile a declarative compose-v2 spec into ordinary scene layers.

The compiler owns terrain snapping/coalescing, band assignment, feet
conversion, y-sorted world z values, per-style auto-scale, and a first-cut
overlap nudge. It resolves asset facts through :mod:`assetrizz_plugin`
library metrics by default, and accepts an injected ``metrics_fn`` so tests
do not need the full library.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .assets import Metrics, full_slug, metrics, target_scale
from .bands import BANDS, SKIP_SLUGS
from .layout import band_z, default_band, topleft_from_feet

_HUD_FALLBACK = {"margin": 32, "top": 128, "right": 360, "bottom": 208, "left": 32}


@dataclass
class Issue:
    """One actionable compiler diagnostic."""

    severity: str
    code: str
    message: str
    subject: str = ""
    fix: str = ""

    def as_dict(self) -> dict[str, Any]:
        body = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.subject:
            body["subject"] = self.subject
        if self.fix:
            body["fix"] = self.fix
        return body

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.as_dict().get(key, default)

    def keys(self):
        return self.as_dict().keys()

    def values(self):
        return self.as_dict().values()

    def items(self):
        return self.as_dict().items()

    def __iter__(self):
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


def _templates() -> dict[str, dict[str, Any]]:
    try:
        from . import templates as templates_module
    except ImportError:
        return _FALLBACK_TEMPLATES
    return templates_module.TEMPLATES


_FALLBACK_TEMPLATES: dict[str, dict[str, Any]] = {
    "topdown_farming": {
        "perspective": "topdown_34",
        "compose": [640, 360],
        "output": [1920, 1080],
        "upscale": 3,
        "grid": 32,
        "tile_size": 32,
        "nearest": True,
        "style": "pixel_32",
        "scale_mode": "native",
        "budgets": {
            "characters": 4,
            "creatures": 5,
            "props": 10,
            "vfx": 1,
            "buildings": 3,
            "foliage": 6,
        },
        "hud": dict(_HUD_FALLBACK),
    },
    "topdown_shooter": {
        "perspective": "topdown",
        "compose": [1920, 1080],
        "output": [1920, 1080],
        "upscale": 1,
        "grid": 64,
        "tile_size": 256,
        "nearest": False,
        "style": "dark_scifi",
        "scale_mode": "target",
        "target_px": {
            "characters": 210,
            "creatures": 120,
            "enemies": 120,
            "props": 110,
            "vehicles": 160,
            "foliage": 180,
            "buildings": 280,
            "furniture": 130,
            "vfx": 90,
            "decals": 80,
            "terrain": 256,
            "tiles": 256,
        },
        "target_px_subject": {"vehicles/air": 150},
        "budgets": {
            "characters": 3,
            "creatures": 2,
            "enemies": 4,
            "props": 8,
            "vfx": 1,
            "buildings": 1,
            "vehicles": 2,
        },
        "hud": dict(_HUD_FALLBACK),
    },
    "dungeon_crawler": {
        "perspective": "topdown_34",
        "compose": [1920, 1080],
        "output": [1920, 1080],
        "upscale": 1,
        "grid": 64,
        "tile_size": 256,
        "nearest": False,
        "style": "hand_painted_fantasy",
        "scale_mode": "target",
        "target_px": {
            "characters": 220,
            "creatures": 130,
            "enemies": 200,
            "props": 120,
            "vehicles": 160,
            "foliage": 200,
            "buildings": 280,
            "furniture": 150,
            "vfx": 90,
            "decals": 90,
        },
        "budgets": {
            "characters": 3,
            "enemies": 4,
            "props": 10,
            "vfx": 3,
            "foliage": 4,
        },
        "hud": dict(_HUD_FALLBACK),
    },
    "side_platformer": {
        "perspective": "side",
        "compose": [1920, 1080],
        "output": [1920, 1080],
        "upscale": 1,
        "grid": 64,
        "tile_size": 256,
        "nearest": False,
        "style": "flat_vector_ui",
        "scale_mode": "target",
        "target_px": {
            "characters": 200,
            "creatures": 90,
            "enemies": 90,
            "props": 80,
            "foliage": 220,
            "vfx": 70,
        },
        "budgets": {
            "characters": 2,
            "enemies": 4,
            "props": 8,
            "vfx": 2,
            "foliage": 10,
        },
        "hud": dict(_HUD_FALLBACK),
    },
}


def merge_template(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Merge a spec over its named template (HUD and budgets merge by key)."""
    name = str(spec.get("template") or "")
    base = dict(_templates().get(name) or {})
    out = dict(base)
    for key, value in spec.items():
        if key == "hud" and isinstance(value, Mapping) and isinstance(out.get("hud"), Mapping):
            hud = dict(out["hud"])
            hud.update(value)
            out["hud"] = hud
        elif key == "budgets" and isinstance(value, Mapping) and isinstance(out.get("budgets"), Mapping):
            budgets = dict(out["budgets"])
            budgets.update(value)
            out["budgets"] = budgets
        else:
            out[key] = value
    if not out.get("style"):
        raise ValueError("spec needs a style or a template that provides one")
    out["compose"] = [int(out.get("compose", [640, 360])[0]), int(out.get("compose", [640, 360])[1])]
    out["grid"] = int(out.get("grid") or 32)
    out.setdefault("output", list(out["compose"]))
    return out


def playfield_world(template: Mapping[str, Any]) -> tuple[int, int, int, int]:
    """Return the playfield rect after HUD dock reservations, in compose px."""
    width, height = (int(v) for v in template.get("compose", [640, 360]))
    docks = template.get("hud") or {}
    if not docks:
        return (0, 0, width, height)
    try:
        from . import hud as hud_module

        output = template.get("output")
        if output and tuple(int(v) for v in output) != (width, height):
            return hud_module.playfield_world(
                width,
                height,
                docks,
                output_size=(int(output[0]), int(output[1])),
            )
        return hud_module.playfield_world(width, height, docks)
    except ImportError:
        values = dict(_HUD_FALLBACK)
        values.update({key: int(value) for key, value in docks.items() if key in values})
        output = template.get("output") or [width, height]
        scale_x = width / int(output[0])
        scale_y = height / int(output[1])
        left = int(round(values["left"] * scale_x))
        top = int(round(values["top"] * scale_y))
        right = width - int(round(values["right"] * scale_x))
        bottom = height - int(round(values["bottom"] * scale_y))
        return left, top, right, bottom


def _coalesce_cells(cells: Sequence[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """Coalesce adjacent grid cells into row runs, then stack matching runs."""
    by_row: dict[int, list[int]] = {}
    for xx, yy in cells:
        by_row.setdefault(int(yy), []).append(int(xx))
    runs: list[tuple[int, int, int, int]] = []
    for yy, xs in sorted(by_row.items()):
        xs = sorted(set(xs))
        if not xs:
            continue
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            runs.append((start, yy, prev - start + 1, 1))
            if x is not None:
                start = prev = x
    merged: list[tuple[int, int, int, int]] = []
    used = [False] * len(runs)
    for index, (col, row, run_w, run_h) in enumerate(runs):
        if used[index]:
            continue
        acc_h = run_h
        for later in range(index + 1, len(runs)):
            other_col, other_row, other_w, other_h = runs[later]
            if other_col == col and other_w == run_w and other_row == row + acc_h:
                used[later] = True
                acc_h += other_h
            elif other_row > row + acc_h:
                break
        merged.append((col, row, run_w, acc_h))
    return merged


def footprint(
    item: Metrics,
    feet_x: float,
    feet_y: float,
    scale: float,
) -> tuple[float, float, float, float]:
    """A conservative ground footprint centered on the feet point."""
    vis_w = item.vis_w * scale
    if item.category in {"characters", "creatures", "enemies"}:
        width = max(24.0, vis_w * 0.85)
        height = max(16.0, vis_w * 0.35)
    elif item.category in {"buildings", "terrain"}:
        width = max(32.0, vis_w * 0.70)
        height = max(20.0, vis_w * 0.25)
    else:
        width = max(16.0, vis_w * 0.50)
        height = max(12.0, vis_w * 0.25)
    return (feet_x - width / 2, feet_y - height, feet_x + width / 2, feet_y)


def rects_overlap(a: Sequence[float], b: Sequence[float], pad: float = 0.0) -> bool:
    return not (
        a[2] + pad <= b[0]
        or b[2] + pad <= a[0]
        or a[3] + pad <= b[1]
        or b[3] + pad <= a[1]
    )


def _background(template: Mapping[str, Any], style: str) -> dict[str, Any]:
    raw = template.get("background")
    if raw is None:
        return {"type": "color", "color": "#141218"}
    if isinstance(raw, Mapping):
        return dict(raw)
    text = str(raw).strip()
    if not text:
        return {"type": "color", "color": "#141218"}
    if text.startswith("#") or text.lower() in {"transparent", "none"}:
        return {"type": "color", "color": text}
    return {"type": "asset", "slug": full_slug(style, text), "mode": "fill"}


def _resolve_at(
    item: Mapping[str, Any],
    slots: Mapping[str, tuple[float, float]],
    grid: int,
) -> tuple[float, float] | None:
    if "slot" in item:
        slot = str(item.get("slot") or "")
        if slot in slots:
            return slots[slot]
        return None
    if "at_px" in item:
        try:
            return float(item["at_px"][0]), float(item["at_px"][1])
        except (TypeError, ValueError, IndexError):
            return None
    if "at" in item:
        try:
            return float(item["at"][0]) * grid, float(item["at"][1]) * grid
        except (TypeError, ValueError, IndexError):
            return None
    return None


def compile_spec(
    spec: Mapping[str, Any] | str,
    *,
    metrics_fn: Callable[[str], Metrics] | None = None,
) -> dict[str, Any]:
    """Compile one declarative scene spec into a layer document plus issues."""
    if isinstance(spec, str):
        spec = json.loads(spec)
    if not isinstance(spec, Mapping):
        raise ValueError("spec must be a JSON object")
    spec = dict(spec)
    template = merge_template(spec)
    style = str(template["style"])
    width, height = (int(v) for v in template["compose"])
    grid = int(template["grid"])
    tile_size = int(template.get("tile_size") or grid)
    nearest = bool(template.get("nearest"))
    resolve = metrics_fn or metrics
    issues: list[Issue] = []
    layers: list[dict[str, Any]] = []
    placements: list[dict[str, Any]] = []

    def add_issue(
        severity: str,
        code: str,
        message: str,
        subject: str = "",
        fix: str = "",
    ) -> None:
        issues.append(Issue(severity, code, message, subject, fix))

    background = _background(template, style)

    for region in template.get("terrain") or []:
        if not isinstance(region, Mapping):
            add_issue("error", "terrain_region", "Terrain entry must be an object")
            continue
        tile = region.get("tile")
        if not tile:
            add_issue("error", "terrain_tile", "Terrain entry needs a tile slug", fix="Add tile=<style path>.")
            continue
        try:
            slug = full_slug(style, str(tile))
        except ValueError as exc:
            add_issue("error", "terrain_tile", str(exc))
            continue
        if slug in SKIP_SLUGS:
            add_issue(
                "error",
                "skipped_asset",
                f"Terrain uses a flagged tile {slug}",
                slug,
                "Pick a clean variant (often *_variant_a).",
            )
            continue
        try:
            item = resolve(slug)
        except Exception as exc:
            add_issue("error", "missing", f"Cannot resolve {slug}: {exc}", slug)
            continue
        if item.style and item.style != style:
            add_issue(
                "error",
                "style_lock",
                f"{slug} is style {item.style}, scene is {style}",
                slug,
                "Search again with this style locked.",
            )
        if item.category != "tiles" and region.get("band") not in {"sky", "terrain"}:
            add_issue("warn", "category", f"Terrain entry is category {item.category}, not tiles", slug)
        z_band = default_band(item, region.get("band"))
        cells: list[tuple[int, int]] = []
        if "rect" in region:
            try:
                col, row, cells_w, cells_h = (int(v) for v in region["rect"])
            except (TypeError, ValueError) as exc:
                add_issue("error", "terrain_rect", f"Bad terrain rect {region['rect']!r}: {exc}", slug)
                continue
            if cells_w <= 0 or cells_h <= 0:
                add_issue("error", "terrain_rect", f"Terrain rect has non-positive size {region['rect']}", slug)
                continue
            for yy in range(row, row + cells_h):
                for xx in range(col, col + cells_w):
                    cells.append((xx, yy))
        for cell in region.get("cells") or []:
            try:
                cells.append((int(cell[0]), int(cell[1])))
            except (TypeError, ValueError, IndexError):
                add_issue("warn", "terrain_cell", f"Ignoring bad terrain cell {cell!r}", slug)
        if not cells:
            add_issue("warn", "empty_terrain", "Terrain region has no cells", slug)
            continue
        for col, row, run_w, run_h in _coalesce_cells(cells):
            layer_id = region.get("id") or f"t_{slug.rsplit('/', 1)[-1]}_{col}_{row}"
            layers.append(
                {
                    "id": str(layer_id),
                    "slug": slug,
                    "x": col * grid,
                    "y": row * grid,
                    "z": band_z(z_band),
                    "scale": 1.0,
                    "flip_x": False,
                    "visible": True,
                    "tile": {"w": run_w * grid, "h": run_h * grid},
                    "tile_cell": tile_size,
                    "nearest": nearest,
                }
            )

    slots: dict[str, tuple[float, float]] = {}
    for name, at in (template.get("slots") or {}).items():
        try:
            slots[str(name)] = (float(at[0]) * grid, float(at[1]) * grid)
        except (TypeError, ValueError, IndexError):
            add_issue("warn", "slot", f"Ignoring bad slot {name!r}", str(name))

    for entry in template.get("place") or []:
        if not isinstance(entry, Mapping):
            add_issue("error", "place_entry", "Place entry must be an object")
            continue
        raw_slug = entry.get("slug")
        if not raw_slug:
            add_issue("error", "place_slug", "Place entry needs a slug", fix="Add slug=<style path>.")
            continue
        try:
            slug = full_slug(style, str(raw_slug))
        except ValueError as exc:
            add_issue("error", "place_slug", str(exc))
            continue
        ident = str(entry.get("id") or slug.rsplit("/", 1)[-1])
        if slug in SKIP_SLUGS:
            add_issue("error", "skipped_asset", f"{ident} uses flagged asset {slug}", ident, "Pick a different slug.")
            continue
        try:
            item = resolve(slug)
        except Exception as exc:
            add_issue("error", "missing", f"Cannot resolve {slug}: {exc}", ident)
            continue
        if item.style and item.style != style:
            add_issue("error", "style_lock", f"{ident} is style {item.style}, scene is {style}", ident)
        at = _resolve_at(entry, slots, grid)
        if at is None:
            add_issue(
                "error",
                "missing_position",
                f"{ident} needs at, at_px, or a known slot",
                ident,
                "Add at=[cell_x, cell_y] or define the slot in slots.",
            )
            continue
        scale = target_scale(item, template, entry.get("scale"))
        band = default_band(item, entry.get("band"), flying=bool(entry.get("flying")))
        placements.append(
            {
                "id": ident,
                "slug": slug,
                "metrics": item,
                "scale": scale,
                "flip_x": bool(entry.get("flip_x")),
                "flip_y": bool(entry.get("flip_y")),
                "band": band,
                "feet": [float(at[0]), float(at[1])],
                "role": entry.get("role") or item.category,
            }
        )

    budgets = dict(template.get("budgets") or {})
    counts: dict[str, int] = {}
    for placement in placements:
        category = placement["metrics"].category
        counts[category] = counts.get(category, 0) + 1
    for category, count in counts.items():
        cap = budgets.get(category)
        if cap is not None and count > cap:
            add_issue(
                "warn",
                "density",
                f"{count} {category} placed, budget is {cap}",
                category,
                f"Remove {count - cap} {category}, or raise the template budget.",
            )

    field = playfield_world(template)
    occupied: list[tuple[str, tuple[float, float, float, float]]] = []
    for placement in placements:
        if placement["band"] != "world":
            continue
        item = placement["metrics"]
        feet_x, feet_y = placement["feet"]
        ground = footprint(item, feet_x, feet_y, placement["scale"])
        hits = [other_id for other_id, other in occupied if rects_overlap(ground, other)]
        if not hits:
            occupied.append((placement["id"], ground))
            continue
        partner = next((other for other_id, other in occupied if other_id in hits), None)
        direction = 1
        if partner is not None:
            direction = 1 if feet_x >= (partner[0] + partner[2]) / 2 else -1
        found: tuple[float, float, tuple[float, float, float, float]] | None = None
        for dx, dy in (
            (direction * grid, 0),
            (direction * grid * 1.5, 0),
            (direction * grid * 2, 0),
            (direction * grid * 2.5, 0),
            (0, grid),
            (0, -grid),
            (direction * grid, grid),
            (direction * grid, -grid),
            (-direction * grid, 0),
            (-direction * grid * 2, 0),
        ):
            new_x, new_y = feet_x + dx, feet_y + dy
            new_ground = footprint(item, new_x, new_y, placement["scale"])
            if any(rects_overlap(new_ground, other) for _, other in occupied):
                continue
            if new_x < field[0] or new_x > field[2] or new_y < field[1] or new_y > field[3]:
                continue
            found = (new_x, new_y, new_ground)
            break
        if found:
            placement["feet"] = [found[0], found[1]]
            placement["nudged"] = True
            add_issue(
                "warn",
                "overlap_nudged",
                f"{placement['id']} overlapped {', '.join(hits)} and was nudged",
                placement["id"],
                "Place with more space, or leave nudging to the compiler.",
            )
            occupied.append((placement["id"], found[2]))
        else:
            add_issue(
                "error",
                "overlap",
                f"{placement['id']} footprint overlaps {', '.join(hits)} and could not be nudged",
                placement["id"],
                "Move one of the actors, or drop the lower-priority one.",
            )
            occupied.append((placement["id"], ground))

    for placement in placements:
        item = placement["metrics"]
        feet_x, feet_y = placement["feet"]
        x, y = topleft_from_feet(item, feet_x, feet_y, placement["scale"], placement["flip_x"])
        scaled_w = int(round(item.width * placement["scale"]))
        scaled_h = int(round(item.height * placement["scale"]))
        layers.append(
            {
                "id": placement["id"],
                "slug": placement["slug"],
                "x": x,
                "y": y,
                "z": band_z(placement["band"], feet_y),
                "scale": placement["scale"],
                "flip_x": placement["flip_x"],
                "flip_y": placement["flip_y"],
                "visible": True,
                "band": placement["band"],
                "feet": [round(feet_x, 1), round(feet_y, 1)],
            }
        )
        if placement["band"] in {"world", "aerial"}:
            if feet_x < field[0] or feet_x > field[2] or feet_y < field[1] or feet_y > field[3]:
                if feet_y < field[1] and item.category in {"foliage", "buildings"}:
                    add_issue(
                        "info",
                        "hud_zone",
                        f"{placement['id']} feet sit in the top margin (often ok for a back row)",
                        placement["id"],
                    )
                else:
                    add_issue(
                        "warn",
                        "hud_zone",
                        f"{placement['id']} feet at ({feet_x:.0f},{feet_y:.0f}) sit in a reserved HUD dock "
                        f"(playfield x {field[0]}-{field[2]}, y {field[1]}-{field[3]})",
                        placement["id"],
                        "Move it into the playfield so the HUD does not cover the subject.",
                    )
        if x + scaled_w < 0 or y + scaled_h < 0 or x > width or y > height:
            add_issue("warn", "off_canvas", f"{placement['id']} is fully outside the canvas", placement["id"])

    if len(layers) > 200:
        add_issue("error", "layer_cap", f"{len(layers)} layers; compose cap is 200", fix="Coalesce terrain, or cut props.")

    used: set[str] = set()
    for layer in layers:
        base = str(layer["id"])
        name = base
        counter = 2
        while name in used:
            name = f"{base}_{counter}"
            counter += 1
        layer["id"] = name
        used.add(name)

    hud_spec = dict(template.get("hud") or {})
    for key in (
        "title",
        "bars",
        "currency",
        "meta_lines",
        "quest_title",
        "quest_lines",
        "dialogue_speaker",
        "dialogue_text",
        "prompts",
        "hotbar",
        "hotbar_selected",
        "panel_widget",
        "dialogue_widget",
        "frame_widget",
        "minimap",
        "radar",
        "title_color",
        "text_color",
        "muted_color",
        "stroke",
        "currency_icon",
    ):
        if key in template:
            hud_spec[key] = template[key]

    result = {
        "id": template.get("id") or spec.get("id") or "scene",
        "width": width,
        "height": height,
        "background": background,
        "layers": layers,
        "layer_count": len(layers),
        "meta": {
            "title": template.get("title") or template.get("id"),
            "genre": template.get("genre") or "",
            "style": style,
            "template": spec.get("template"),
            "perspective": template.get("perspective"),
            "compose_size": [width, height],
            "output_size": list(template.get("output") or [width, height]),
            "upscale": template.get("upscale") or 1,
            "grid": grid,
            "tile_size": tile_size,
            "playfield_world": list(field),
            "scale_mode": template.get("scale_mode"),
            "notes": "Compiled by compose-v2 (bands, grid terrain, feet y-sort, auto-scale, HUD docks).",
        },
        "hud": hud_spec,
        "template": template,
        "placements": [
            {
                "id": placement["id"],
                "slug": placement["slug"],
                "band": placement["band"],
                "feet": placement["feet"],
                "scale": round(float(placement["scale"]), 4),
                "category": placement["metrics"].category,
                "nudged": bool(placement.get("nudged")),
            }
            for placement in placements
        ],
        "issues": issues,
        "ok": not any(issue.severity == "error" for issue in issues),
    }

    try:
        from .lint import lint_compiled
    except ImportError:
        linted: list[Issue] = []
    else:
        linted = lint_compiled(
            result,
            spec=spec,
            metrics_fn=resolve,
            skip_codes=(
                "overlap",
                "density",
                "hud_zone",
                "off_canvas",
                "style_lock",
                "layer_cap",
            ),
        )
    if linted:
        seen = {(issue.code, issue.subject) for issue in result["issues"]}
        for issue in linted:
            key = (issue.code, issue.subject)
            if key in seen:
                continue
            seen.add(key)
            result["issues"].append(issue)
        result["ok"] = not any(
            issue.severity == "error" for issue in result["issues"]
        )
    return result
