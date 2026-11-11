"""World rasterization for compiled compose-v2 scenes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from assets import engine_compose, metrics, open_slug, tight_tile, tile_image
from hud import draw_hud


def render_world(doc: dict[str, Any]) -> Image.Image:
    width, height = int(doc["width"]), int(doc["height"])
    tmpl = doc.get("template") or {}
    nearest_default = bool(tmpl.get("nearest"))
    tile_layers = [ly for ly in doc["layers"] if ly.get("tile")]
    sprite_layers = [ly for ly in doc["layers"] if not ly.get("tile")]

    scratch = {
        "id": doc["id"],
        "width": width,
        "height": height,
        "background": doc.get("background") or {"type": "color", "color": "#141218"},
        "layers": [],
    }
    canvas = engine_compose(scratch).convert("RGBA")

    for ly in sorted(tile_layers, key=lambda i: (int(i.get("z") or 0), str(i.get("id") or ""))):
        if not ly.get("visible", True):
            continue
        m = metrics(ly["slug"])
        nearest = bool(ly.get("nearest", nearest_default or m.width <= 128))
        tile_cell = int(ly.get("tile_cell") or m.width)
        src = open_slug(ly["slug"])
        tile = tight_tile(src, tile_cell, nearest=nearest)
        tw, th = int(ly["tile"]["w"]), int(ly["tile"]["h"])
        filled = tile_image(tile, tw, th)
        x, y = int(ly.get("x") or 0), int(ly.get("y") or 0)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay.paste(filled, (x, y), filled)
        canvas.alpha_composite(overlay)

    sprite_doc = {
        "id": doc["id"],
        "width": width,
        "height": height,
        "background": {"type": "color", "color": "transparent"},
        "layers": sprite_layers,
    }
    sprites = engine_compose(sprite_doc).convert("RGBA")
    canvas.alpha_composite(sprites)
    return canvas


def upscale(im: Image.Image, factor: int, nearest: bool) -> Image.Image:
    if factor == 1:
        return im
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return im.resize((im.width * factor, im.height * factor), resample)


def render_compiled(compiled: dict[str, Any], out_png: Path) -> dict[str, Any]:
    world = render_world(compiled)
    tmpl = compiled.get("template") or {}
    factor = int(tmpl.get("upscale") or compiled["meta"].get("upscale") or 1)
    nearest = bool(tmpl.get("nearest"))
    frame = upscale(world, factor, nearest)
    target = tuple(tmpl.get("output") or compiled["meta"]["output_size"])
    if frame.size != tuple(target):
        resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
        frame = frame.resize(tuple(target), resample)
    draw_hud(frame, compiled)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    frame.save(out_png, format="PNG", optimize=True)
    return {"png": str(out_png), "size": list(frame.size), "issues": compiled.get("issues") or []}
