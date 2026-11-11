"""Template-aware lint for compose-v2 documents.

``lint_compiled`` inspects the document returned by
:func:`assetrizz_plugin.compose_v2.compile.compile_spec`; ``lint_legacy``
inspects a flat v1 scene document. Both return :class:`Issue` objects with a
``severity``, ``code``, ``message``, ``subject``, and actionable ``fix``.

Asset facts are resolved through an injected ``metrics_fn`` so tests never
need the large local library or the network.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Sequence

from . import compile as compile_module
from .assets import Metrics
from .compile import Issue, footprint, playfield_world, rects_overlap
from .hud import HUD_DOCKS
from .layout import feet_from_topleft
from .templates import TEMPLATES

_DEFAULT_LAYER_CAP = 200
_ACTOR_CATEGORIES = frozenset({"characters", "creatures", "enemies"})
_OVERLAP_SKIP = frozenset({"decals", "vfx", "effects", "tiles", "backgrounds"})
_BACK_ROW_CATEGORIES = frozenset({"foliage", "buildings"})
_TARGET_SCALE_SKIP = frozenset({"tiles", "backgrounds", "decals", "vfx", "effects"})
_WALL_PURPOSES = frozenset({"wall", "backdrop", "boundary", "fence"})


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolver(
    metrics_fn: Callable[[str], Metrics] | None,
) -> Callable[[str], Metrics | None]:
    resolve = metrics_fn or compile_module.metrics
    cache: dict[str, Metrics | None] = {}

    def get(slug: str) -> Metrics | None:
        if not slug:
            return None
        if slug not in cache:
            try:
                cache[slug] = resolve(slug)
            except Exception:
                cache[slug] = None
        return cache[slug]

    return get


def _wall_is_floor(
    layer: Mapping[str, Any],
    item: Metrics,
    canvas_height: int,
    regions: Mapping[str, Mapping[str, Any]],
) -> bool:
    """True when a wall tile is stamped as walkable ground rather than a back wall."""
    region = regions.get(str(layer.get("id") or ""))
    if region is not None:
        if str(region.get("purpose") or "").lower() in _WALL_PURPOSES:
            return False
        if region.get("band") == "sky":
            return False
    if item.subcategory != "wall":
        return False

    tile = layer.get("tile")
    x = _int(layer.get("x"))
    y = _int(layer.get("y"))
    if isinstance(tile, Mapping):
        tile_w = _int(tile.get("w"))
        tile_h = _int(tile.get("h"))
        if tile_h and tile_h < item.height and y > canvas_height * 0.25:
            return True
        if tile_w and tile_w > item.width * 1.5:
            return True
        if tile_h and tile_h > item.height * 1.5:
            return True
        return False

    band = layer.get("band")
    return band is None or band in {"world", "terrain"}


def _records(
    compiled: Mapping[str, Any],
    layers: Sequence[Mapping[str, Any]],
    get: Callable[[str], Metrics | None],
) -> list[dict[str, Any]]:
    raw = compiled.get("placements")
    records: list[dict[str, Any]] = []
    if raw:
        for entry in raw:
            if not isinstance(entry, Mapping):
                continue
            record = dict(entry)
            item = get(str(record.get("slug") or ""))
            if not record.get("category") and item is not None:
                record["category"] = item.category
            records.append(record)
        return records

    for layer in layers:
        if "tile" in layer:
            continue
        feet = layer.get("feet")
        if not feet:
            continue
        item = get(str(layer.get("slug") or ""))
        records.append(
            {
                "id": layer.get("id"),
                "slug": layer.get("slug"),
                "band": layer.get("band"),
                "feet": feet,
                "scale": layer.get("scale", 1.0),
                "category": item.category if item is not None else "",
            }
        )
    return records


def lint_compiled(
    compiled: Mapping[str, Any],
    *,
    spec: Mapping[str, Any] | None = None,
    metrics_fn: Callable[[str], Metrics] | None = None,
    skip_codes: Sequence[str] = (),
) -> list[Issue]:
    """Return template-aware issues for one compiled compose-v2 document.

    ``skip_codes`` lets the compiler avoid re-reporting diagnostics it
    already owns; standalone callers get every check.
    """
    if not isinstance(compiled, Mapping):
        raise ValueError("compiled must be a scene mapping")

    skip = set(skip_codes)
    issues: list[Issue] = []

    def add(
        severity: str,
        code: str,
        message: str,
        subject: str = "",
        fix: str = "",
    ) -> None:
        if code in skip:
            return
        issues.append(Issue(severity, code, message, subject, fix))

    template = dict(compiled.get("template") or {})
    meta = dict(compiled.get("meta") or {})
    style = str(meta.get("style") or template.get("style") or "")
    width = _int(compiled.get("width") or (meta.get("compose_size") or [0, 0])[0])
    height = _int(compiled.get("height") or (meta.get("compose_size") or [0, 0])[1])
    grid = _int(template.get("grid") or meta.get("grid"), 32)
    name = str(meta.get("template") or (spec or {}).get("template") or "")
    if name and name not in TEMPLATES:
        add(
            "error",
            "unknown_template",
            f"Unknown template {name!r}",
            name,
            f"Use one of: {', '.join(sorted(TEMPLATES))}.",
        )

    get = _resolver(metrics_fn)
    layers = [
        layer
        for layer in compiled.get("layers") or []
        if isinstance(layer, Mapping) and layer.get("visible", True)
    ]
    records = _records(compiled, layers, get)

    try:
        field = tuple(int(value) for value in (meta.get("playfield_world") or playfield_world(template)))
    except (TypeError, ValueError):
        field = (0, 0, width, height)
    if len(field) != 4:
        field = (0, 0, width, height)

    docks = template.get("hud") or {}
    if isinstance(docks, Mapping):
        for key in ("margin", "top", "right", "bottom", "left"):
            if key in docks and _int(docks[key]) < 0:
                add(
                    "error",
                    "hud_dock",
                    f"HUD dock {key!r} must not be negative",
                    key,
                    "Use zero or a positive reserve, or drop the dock from the template.",
                )
        if field[0] >= field[2] or field[1] >= field[3]:
            add(
                "error",
                "hud_dock",
                "HUD docks reserve the whole compose canvas",
                "",
                "Reduce the dock sizes or increase the compose size.",
            )

    cap = _int(template.get("layer_cap"), _DEFAULT_LAYER_CAP)
    if len(layers) > cap:
        add(
            "error",
            "layer_cap",
            f"{len(layers)} layers; compose cap is {cap}",
            "",
            "Coalesce terrain runs into fewer layers, or cut low-priority props.",
        )

    regions: dict[str, Mapping[str, Any]] = {}
    if isinstance(spec, Mapping):
        for region in spec.get("terrain") or []:
            if isinstance(region, Mapping) and region.get("id"):
                regions[str(region["id"])] = region

    background = compiled.get("background")
    if isinstance(background, Mapping) and background.get("type") == "asset":
        item = get(str(background.get("slug") or ""))
        if item is not None and item.style and style and item.style != style:
            add(
                "error",
                "style_lock",
                f"Background is style {item.style}, scene is {style}",
                "background",
                "Lock one style pack and re-search the background with that style.",
            )

    for layer in layers:
        slug = str(layer.get("slug") or "")
        item = get(slug)
        subject = str(layer.get("id") or slug)
        if item is not None and item.style and style and item.style != style:
            add(
                "error",
                "style_lock",
                f"{subject} is style {item.style}, scene is {style}",
                subject,
                "Lock one style pack and re-search the asset with that style.",
            )

        if item is not None and _wall_is_floor(layer, item, height, regions):
            add(
                "warn",
                "wall_as_floor",
                f"Wall tile {slug} is used as ground at "
                f"({_int(layer.get('x'))},{_int(layer.get('y'))})",
                subject,
                "Use a floor tile for walkable ground, and reserve wall tiles for "
                "vertical back walls (mark the region purpose='wall' if intentional).",
            )

        tile = layer.get("tile")
        if isinstance(tile, Mapping) and item is not None and item.category == "tiles":
            if grid > 0 and (_int(layer.get("x")) % grid or _int(layer.get("y")) % grid):
                add(
                    "info",
                    "grid_misalign",
                    f"{subject} is not aligned to the {grid}px template grid",
                    subject,
                    f"Snap terrain cells to multiples of {grid}.",
                )

        if isinstance(tile, Mapping):
            layer_w = _int(tile.get("w"), item.width if item is not None else 0)
            layer_h = _int(tile.get("h"), item.height if item is not None else 0)
        elif item is not None:
            scale = _float(layer.get("scale"), 1.0)
            layer_w = int(round(item.width * scale))
            layer_h = int(round(item.height * scale))
        else:
            continue
        x = _int(layer.get("x"))
        y = _int(layer.get("y"))
        if x + layer_w < 0 or y + layer_h < 0 or x > width or y > height:
            add(
                "warn",
                "off_canvas",
                f"{subject} is fully outside the {width}x{height} canvas",
                subject,
                "Move it inside the canvas, or remove it from the spec.",
            )

    budgets = dict(template.get("budgets") or {})
    counts: dict[str, int] = {}
    for record in records:
        category = str(record.get("category") or "")
        if not category:
            item = get(str(record.get("slug") or ""))
            category = item.category if item is not None else ""
        if category:
            counts[category] = counts.get(category, 0) + 1
    for category, count in sorted(counts.items()):
        budget = budgets.get(category)
        if budget is None:
            continue
        budget = _int(budget)
        if count > budget:
            add(
                "warn",
                "density",
                f"{count} {category} placed, budget is {budget}"
                + (f" for {name}" if name else ""),
                category,
                f"Remove {count - budget} {category}, or raise the template budget.",
            )

    world: list[tuple[str, str, tuple[float, float], tuple[float, float, float, float]]] = []
    for record in records:
        if str(record.get("band") or "") != "world":
            continue
        item = get(str(record.get("slug") or ""))
        if item is None or item.category in _OVERLAP_SKIP:
            continue
        feet = record.get("feet") or []
        try:
            feet_x, feet_y = float(feet[0]), float(feet[1])
        except (TypeError, ValueError, IndexError):
            continue
        scale = _float(record.get("scale"), 1.0)
        world.append(
            (
                str(record.get("id") or record.get("slug") or ""),
                item.category,
                (feet_x, feet_y),
                footprint(item, feet_x, feet_y, scale),
            )
        )
    for index, (ident_a, _cat_a, _feet_a, rect_a) in enumerate(world):
        for ident_b, _cat_b, _feet_b, rect_b in world[index + 1 :]:
            if rects_overlap(rect_a, rect_b):
                add(
                    "error",
                    "overlap",
                    f"{ident_a} footprint overlaps {ident_b}",
                    ident_a,
                    f"Space {ident_a} and {ident_b} at least half a sprite apart, "
                    "or drop the lower-priority one.",
                )

    for record in records:
        band = str(record.get("band") or "")
        if band not in {"world", "aerial"}:
            continue
        feet = record.get("feet") or []
        try:
            feet_x, feet_y = float(feet[0]), float(feet[1])
        except (TypeError, ValueError, IndexError):
            continue
        if field[0] <= feet_x <= field[2] and field[1] <= feet_y <= field[3]:
            continue
        item = get(str(record.get("slug") or ""))
        category = item.category if item is not None else str(record.get("category") or "")
        subject = str(record.get("id") or record.get("slug") or "")
        if feet_y < field[1] and category in _BACK_ROW_CATEGORIES:
            add(
                "info",
                "hud_zone",
                f"{subject} feet sit in the top margin (often ok for a back row)",
                subject,
                "Keep the subject inside the playfield; back-row foliage may stay "
                "in the top margin.",
            )
        else:
            add(
                "warn",
                "hud_zone",
                f"{subject} feet at ({feet_x:.0f},{feet_y:.0f}) sit outside the "
                f"playfield (x {field[0]}-{field[2]}, y {field[1]}-{field[3]})",
                subject,
                "Move it into the playfield so the HUD does not cover the subject.",
            )

    scales: dict[str, list[float]] = {}
    for record in records:
        item = get(str(record.get("slug") or ""))
        category = item.category if item is not None else str(record.get("category") or "")
        if not category or category in _TARGET_SCALE_SKIP:
            continue
        scales.setdefault(category, []).append(_float(record.get("scale"), 1.0))
    for category, values in sorted(scales.items()):
        if len(values) < 2:
            continue
        low, high = min(values), max(values)
        if high > 0 and (high - low) / high > 0.25:
            add(
                "warn",
                "scale_mismatch",
                f"{category} scales range {low:.2f}-{high:.2f} "
                f"({(high - low) / high:.0%} spread)",
                category,
                f"Normalize {category} to the template target_px height, or set "
                "one explicit scale for the category.",
            )

    if template.get("single_ground_plane"):
        bg = compiled.get("background")
        has_floor = any(
            "tile" in layer and "/tiles/floor/" in str(layer.get("slug") or "")
            for layer in layers
        )
        if isinstance(bg, Mapping) and bg.get("type") == "asset" and has_floor:
            add(
                "warn",
                "perspective",
                "A painted background is composited under an orthographic tiled floor",
                "background",
                "Pick one ground plane: keep the painted backdrop alone, or replace "
                "it with the tiled floor.",
            )

    return issues


def lint_legacy(
    doc: Mapping[str, Any] | str,
    *,
    metrics_fn: Callable[[str], Metrics] | None = None,
) -> list[Issue]:
    """Return issues for a flat v1 scene document (top-left x/y plus explicit z)."""
    if isinstance(doc, str):
        doc = json.loads(doc)
    if not isinstance(doc, Mapping):
        raise ValueError("legacy document must be a mapping")

    issues: list[Issue] = []

    def add(
        severity: str,
        code: str,
        message: str,
        subject: str = "",
        fix: str = "",
    ) -> None:
        issues.append(Issue(severity, code, message, subject, fix))

    width = _int(doc.get("width"))
    height = _int(doc.get("height"))
    meta = dict(doc.get("meta") or {})
    style = str(meta.get("style") or doc.get("style") or "")
    raw_upscale = meta.get("upscale")
    if isinstance(raw_upscale, Mapping):
        upscale = _int(raw_upscale.get("factor"), 3 if width <= 800 else 1)
    else:
        upscale = _int(raw_upscale, 3 if width <= 800 else 1)
    output = meta.get("output_size") or [width * upscale, height * upscale]
    try:
        out_w, out_h = int(output[0]), int(output[1])
    except (TypeError, ValueError, IndexError):
        out_w, out_h = width * upscale, height * upscale

    if width > 0 and height > 0 and out_w > 0 and out_h > 0:
        scale_x, scale_y = out_w / width, out_h / height
        field = (
            int(round(HUD_DOCKS["left"] / scale_x)),
            int(round(HUD_DOCKS["top"] / scale_y)),
            width - int(round(HUD_DOCKS["right"] / scale_x)),
            height - int(round(HUD_DOCKS["bottom"] / scale_y)),
        )
    else:
        field = (0, 0, width, height)

    get = _resolver(metrics_fn)
    layers = [
        layer
        for layer in doc.get("layers") or []
        if isinstance(layer, Mapping) and layer.get("visible", True)
    ]

    if len(layers) > _DEFAULT_LAYER_CAP:
        add(
            "error",
            "layer_cap",
            f"{len(layers)} layers; compose cap is {_DEFAULT_LAYER_CAP}",
            "",
            "Coalesce tiled ground, or cut low-priority props.",
        )

    styles: set[str] = set()
    counts: dict[str, int] = {}
    scales: dict[str, list[float]] = {}
    actors: list[dict[str, Any]] = []
    offgrid = 0
    vfx = 0

    for layer in layers:
        slug = str(layer.get("slug") or "")
        if not slug:
            continue
        subject = str(layer.get("id") or slug)
        item = get(slug)
        if item is None:
            add(
                "error",
                "missing",
                f"Cannot resolve {slug}",
                subject,
                "Use a slug from assetrizz_search, or drop the layer.",
            )
            continue
        if item.style:
            styles.add(item.style)
        counts[item.category] = counts.get(item.category, 0) + 1
        scale = _float(layer.get("scale"), 1.0)
        x = _int(layer.get("x"))
        y = _int(layer.get("y"))
        tile = layer.get("tile")

        if isinstance(tile, Mapping):
            tile_w = _int(tile.get("w"))
            tile_h = _int(tile.get("h"))
            step = min(item.width, 32 if item.width <= 64 else 64)
            if item.category == "tiles" and step and (x % step or y % step):
                offgrid += 1
            if item.subcategory == "wall" and tile_h < item.height and y > height * 0.25:
                add(
                    "warn",
                    "wall_as_floor",
                    f"Wall tile {slug} is stamped as a {tile_w}x{tile_h} mid-floor "
                    f"patch at ({x},{y})",
                    subject,
                    "Use props (crates, barrels) for cover, and wall tiles only as a "
                    "back wall or lip.",
                )
            if x + tile_w < 0 or y + tile_h < 0 or x > width or y > height:
                add(
                    "warn",
                    "off_canvas",
                    f"{subject} is fully outside the {width}x{height} canvas",
                    subject,
                    "Move it inside the canvas, or drop the layer.",
                )
            continue

        if item.category in {"vfx", "effects"}:
            vfx += 1
        scales.setdefault(item.category, []).append(scale)
        feet_x, feet_y = feet_from_topleft(
            item, x, y, scale, bool(layer.get("flip_x"))
        )
        actors.append(
            {
                "id": subject,
                "slug": slug,
                "cat": item.category,
                "scale": scale,
                "z": _int(layer.get("z")),
                "feet": (feet_x, feet_y),
                "fp": footprint(item, feet_x, feet_y, scale),
            }
        )
        if (
            x + int(round(item.width * scale)) < 0
            or y + int(round(item.height * scale)) < 0
            or x > width
            or y > height
        ):
            add(
                "warn",
                "off_canvas",
                f"{subject} is fully outside the {width}x{height} canvas",
                subject,
                "Move it inside the canvas, or drop the layer.",
            )

    if len(styles) > 1 or (style and any(other != style for other in styles)):
        add(
            "error",
            "style_lock",
            f"Scene mixes styles {sorted(styles)}"
            + (f" with {style}" if style and len(styles) == 1 else ""),
            "",
            "Lock one style pack and re-search every asset with that style.",
        )

    if vfx > 2:
        add(
            "warn",
            "density",
            f"{vfx} VFX stamps; more than 1-2 turns into visual noise",
            "vfx",
            "Keep one effect tied to a single event.",
        )
    if offgrid:
        add(
            "info",
            "offgrid",
            f"{offgrid} tiled regions are not aligned to the tile size",
            "",
            "Snap tiled layers to the tile grid so seams do not shimmer.",
        )

    for index, actor in enumerate(actors):
        if actor["cat"] in _OVERLAP_SKIP:
            continue
        for other in actors[index + 1 :]:
            if other["cat"] in _OVERLAP_SKIP:
                continue
            if not rects_overlap(actor["fp"], other["fp"]):
                continue
            add(
                "error",
                "overlap",
                f"{actor['id']} footprint overlaps {other['id']}"
                + (
                    " (a character or creature shares the ground point)"
                    if actor["cat"] in _ACTOR_CATEGORIES
                    or other["cat"] in _ACTOR_CATEGORIES
                    else ""
                ),
                actor["id"],
                "Space feet at least half a sprite apart, or drop the "
                "lower-priority actor.",
            )

    charlike = [actor for actor in actors if actor["cat"] in _ACTOR_CATEGORIES]
    if charlike:
        low_props = [
            actor
            for actor in actors
            if actor["cat"] in {"props", "foliage", "buildings"}
        ]
        if all(actor["z"] >= 50 for actor in charlike) and any(
            actor["z"] < 50 for actor in low_props
        ):
            add(
                "warn",
                "z_band",
                "Characters use a high fixed z (always on top) while props use a "
                "low z; a character behind a tree or crate still draws in front",
                "",
                "Put props, foliage, buildings, and characters in one WORLD band "
                "and y-sort by feet.",
            )

    for category, values in sorted(scales.items()):
        if category in {"tiles", "backgrounds"} or len(values) < 2:
            continue
        low, high = min(values), max(values)
        if high > 0 and category in {"characters", "props", "enemies", "creatures"}:
            if (high - low) / high > 0.25:
                add(
                    "warn",
                    "scale_mismatch",
                    f"{category} scales range {low:.2f}-{high:.2f} "
                    f"({(high - low) / high:.0%} spread)",
                    category,
                    "Normalize each category to one target height in the style "
                    "profile.",
                )

    for actor in actors:
        if actor["cat"] in {"decals", "vfx", "effects"}:
            continue
        feet_x, feet_y = actor["feet"]
        if not (
            field[0] <= feet_x <= field[2] and field[1] <= feet_y <= field[3]
        ):
            add(
                "warn",
                "hud_zone",
                f"{actor['id']} feet at ({feet_x:.0f},{feet_y:.0f}) sit in a "
                f"reserved HUD dock (playfield x {field[0]}-{field[2]}, "
                f"y {field[1]}-{field[3]})",
                actor["id"],
                "Anchor the HUD to the edges, and keep the subject in the "
                "remaining playfield.",
            )

    summary = ", ".join(
        f"{category}={count}"
        for category, count in sorted(counts.items())
        if category
    )
    if summary:
        add(
            "info",
            "counts",
            f"Category counts: {summary}",
            "",
            "Use the genre template budgets to trim the largest category.",
        )

    has_background = any(
        "/backgrounds/scene/" in str(layer.get("slug") or "") for layer in layers
    )
    has_floor = any(
        "/tiles/floor/" in str(layer.get("slug") or "") for layer in layers
    )
    if has_background and has_floor:
        add(
            "warn",
            "perspective",
            "A painted/photo background is composited under an orthographic tiled "
            "floor; the two spatial systems fight at the floor/wall join",
            "background",
            "Pick one ground plane. For a painted hall, do not tile a walkable "
            "floor over it.",
        )

    return issues
