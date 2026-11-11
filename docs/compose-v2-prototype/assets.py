"""Library access, metrics, tiling, and 9-slice panels."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bands import SKIP_SLUGS

ROOT_PLUGIN = Path(".")  # BOX-LOCAL prototype path; do not copy
LIBRARY = Path(".")  # BOX-LOCAL prototype library; use plugin get_asset instead
HOME = Path(".")  # BOX-LOCAL prototype home; do not copy

os.environ["ASSETRIZZ_LIBRARY"] = str(LIBRARY)
os.environ["ASSETRIZZ_HOME"] = str(HOME)
os.environ["ASSETRIZZ_ASSET_MODE"] = "local"
os.environ.setdefault("ASSETRIZZ_OFFLINE", "1")

if str(ROOT_PLUGIN) not in sys.path:
    sys.path.insert(0, str(ROOT_PLUGIN))

from assetrizz_plugin.library import resolve_asset  # noqa: E402
from assetrizz_plugin.scene import compose as engine_compose  # noqa: E402

FONT_GOOGLE = Path("/usr/share/fonts/truetype/sand-box/google")
FONT_CUSTOM = Path("/usr/share/fonts/truetype/sand-box/custom")
FONT_DEJAVU = Path("/usr/share/fonts/truetype/dejavu")


@dataclass
class Metrics:
    slug: str
    path: str
    file: Path
    width: int
    height: int
    bbox: tuple[int, int, int, int]
    vis_w: int
    vis_h: int
    category: str
    subcategory: str
    style: str
    pivot: tuple[float, float]
    tileable: bool


_METRICS: dict[str, Metrics] = {}
_IMAGE: dict[str, Image.Image] = {}


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.truetype(str(FONT_DEJAVU / "DejaVuSans.ttf"), size=size)


def fonts_for(style: str):
    if style == "pixel_32":
        p = FONT_GOOGLE / "Press Start 2P" / "PressStart2P-Regular.ttf"
        return font(p, 22), font(p, 14), font(p, 10)
    if style == "dark_scifi":
        title = FONT_GOOGLE / "IBM Plex Mono" / "IBMPlexMono-Bold.ttf"
        body = FONT_GOOGLE / "IBM Plex Mono" / "IBMPlexMono-SemiBold.ttf"
        small = FONT_GOOGLE / "IBM Plex Mono" / "IBMPlexMono-Regular.ttf"
        return font(title, 36), font(body, 18), font(small, 15)
    if style == "hand_painted_fantasy":
        title = FONT_GOOGLE / "IBM Plex Serif" / "IBMPlexSerif-Bold.ttf"
        body_b = FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Semibold.ttf"
        body = FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Regular.ttf"
        return font(title, 44), font(body_b, 22), font(body, 18)
    title = FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Bold.ttf"
    body = FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Semibold.ttf"
    small = FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Regular.ttf"
    return font(title, 42), font(body, 22), font(small, 18)


def full_slug(style: str, slug: str) -> str:
    slug = slug.strip()
    if slug.startswith(style + "/"):
        return slug
    if "/" in slug:
        return f"{style}/{slug}"
    raise ValueError(f"slug must be style-prefixed or a path under the style: {slug!r}")


def metrics(slug: str) -> Metrics:
    if slug in _METRICS:
        return _METRICS[slug]
    if slug in SKIP_SLUGS or "/hedge" in slug:
        raise RuntimeError(f"refusing skipped asset: {slug}")
    asset = resolve_asset(slug=slug)
    path = Path(asset["file"])
    im = Image.open(path).convert("RGBA")
    bb = im.split()[-1].getbbox() or (0, 0, im.width, im.height)
    pivot = asset.get("pivot") or {"x": 0.5, "y": 1.0}
    if isinstance(pivot, str):
        try:
            pivot = json.loads(pivot)
        except json.JSONDecodeError:
            pivot = {"x": 0.5, "y": 1.0}
    px = float(pivot.get("x", 0.5) if isinstance(pivot, dict) else 0.5)
    py = float(pivot.get("y", 1.0) if isinstance(pivot, dict) else 1.0)
    cat = str(asset.get("category") or (slug.split("/")[1] if "/" in slug else ""))
    sub = str(asset.get("subcategory") or "")
    style = str(asset.get("style_pack") or slug.split("/")[0])
    m = Metrics(
        slug=slug,
        path=str(asset.get("path") or ""),
        file=path,
        width=im.width,
        height=im.height,
        bbox=(int(bb[0]), int(bb[1]), int(bb[2]), int(bb[3])),
        vis_w=int(bb[2] - bb[0]),
        vis_h=int(bb[3] - bb[1]),
        category=cat,
        subcategory=sub,
        style=style,
        pivot=(px, py),
        tileable=bool(asset.get("tileable")),
    )
    _METRICS[slug] = m
    _IMAGE[slug] = im
    return m


def open_slug(slug: str) -> Image.Image:
    metrics(slug)
    return _IMAGE[slug].copy()


def tight_tile(im: Image.Image, size: int, nearest: bool) -> Image.Image:
    bb = im.split()[-1].getbbox() or (0, 0, im.width, im.height)
    crop = im.crop(bb)
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    if crop.size != (size, size):
        crop = crop.resize((size, size), resample)
    return crop


def tile_image(tile: Image.Image, width: int, height: int) -> Image.Image:
    canvas = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    tw, th = tile.size
    if tw <= 0 or th <= 0:
        return canvas
    for y in range(0, height, th):
        for x in range(0, width, tw):
            canvas.paste(tile, (x, y), tile)
    return canvas


def nine_slice_tiled(
    im: Image.Image,
    width: int,
    height: int,
    inset: int | tuple[int, int, int, int],
    *,
    nearest: bool,
    fill: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    """9-slice that tiles edges/center instead of stretching, optional solid well."""
    im = im.convert("RGBA")
    src_w, src_h = im.size
    if isinstance(inset, int):
        l = t = r = b = inset
    else:
        l, t, r, b = inset
    l = max(1, min(l, src_w // 2 - 1))
    r = max(1, min(r, src_w - l - 1))
    t = max(1, min(t, src_h // 2 - 1))
    b = max(1, min(b, src_h - t - 1))
    width = max(width, l + r + 1)
    height = max(height, t + b + 1)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    def blit(src_box, dest, mode: str) -> None:
        piece = im.crop(src_box)
        dw, dh = dest[2] - dest[0], dest[3] - dest[1]
        if dw <= 0 or dh <= 0:
            return
        if mode == "corner":
            if piece.size != (dw, dh):
                resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
                piece = piece.resize((dw, dh), resample)
            out.paste(piece, (dest[0], dest[1]), piece)
            return
        region = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
        pw, ph = piece.size
        if mode == "edge_h":
            if ph != dh:
                resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
                piece = piece.resize((max(1, pw), dh), resample)
                pw, ph = piece.size
            x = 0
            while x < dw:
                region.paste(piece, (x, 0), piece)
                x += pw
        elif mode == "edge_v":
            if pw != dw:
                resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
                piece = piece.resize((dw, max(1, ph)), resample)
                pw, ph = piece.size
            y = 0
            while y < dh:
                region.paste(piece, (0, y), piece)
                y += ph
        else:
            y = 0
            while y < dh:
                x = 0
                while x < dw:
                    region.paste(piece, (x, y), piece)
                    x += pw
                y += ph
        out.paste(region, (dest[0], dest[1]), region)

    blit((0, 0, l, t), (0, 0, l, t), "corner")
    blit((src_w - r, 0, src_w, t), (width - r, 0, width, t), "corner")
    blit((0, src_h - b, l, src_h), (0, height - b, l, height), "corner")
    blit((src_w - r, src_h - b, src_w, src_h), (width - r, height - b, width, height), "corner")
    blit((l, 0, src_w - r, t), (l, 0, width - r, t), "edge_h")
    blit((l, src_h - b, src_w - r, src_h), (l, height - b, width - r, height), "edge_h")
    blit((0, t, l, src_h - b), (0, t, l, height - b), "edge_v")
    blit((src_w - r, t, src_w, src_h - b), (width - r, t, width, height - b), "edge_v")
    if fill is not None:
        well = Image.new("RGBA", (width - l - r, height - t - b), fill)
        out.paste(well, (l, t))
    else:
        blit((l, t, src_w - r, src_h - b), (l, t, width - r, height - t), "tile")
    return out


def sample_well_color(im: Image.Image, inset: int) -> tuple[int, int, int, int]:
    w, h = im.size
    box = (inset, inset, max(inset + 1, w - inset), max(inset + 1, h - inset))
    crop = im.convert("RGBA").crop(box)
    pixels = [p for p in crop.getdata() if p[3] >= 200]
    if not pixels:
        return (28, 24, 22, 230)
    channels = list(zip(*pixels))
    mid = len(pixels) // 2

    def med(ch):
        s = sorted(ch)
        return s[mid]

    return (med(channels[0]), med(channels[1]), med(channels[2]), 240)


def scale_img(im: Image.Image, scale: float, nearest: bool) -> Image.Image:
    if abs(scale - 1.0) < 1e-6:
        return im
    w = max(1, int(round(im.width * scale)))
    h = max(1, int(round(im.height * scale)))
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return im.resize((w, h), resample)
