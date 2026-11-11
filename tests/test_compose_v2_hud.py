"""Compose-v2 HUD docks, tiled 9-slice panels, and HUD text.

All images are synthetic and built in memory; no library, network, or
production UI PNG is required.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assetrizz_plugin.compose_v2.hud import (  # noqa: E402
    HUD_DOCKS,
    draw_hud,
    nine_slice_tiled,
    playfield_world,
    sample_well_color,
    wrap_text,
)


def _pattern_panel(size: int = 18, inset: tuple[int, int, int, int] = (5, 3, 4, 6)) -> Image.Image:
    """Synthetic 9-slice panel with uniquely varying edges and a checker well."""
    left, top, right, bottom = inset
    image = Image.new("RGBA", (size, size), (200, 60, 70, 255))
    draw = ImageDraw.Draw(image)
    centre = (left, top, size - right - 1, size - bottom - 1)
    draw.rectangle(centre, fill=(0, 0, 0, 255))
    for x in range(left, size - right):
        image.putpixel((x, 0), (x * 10 % 256, 30, 200, 255))
        image.putpixel((x, size - 1), (x * 7 % 256, 180, 40, 255))
    for y in range(top, size - bottom):
        image.putpixel((0, y), (40, y * 9 % 256, 160, 255))
        image.putpixel((size - 1, y), (200, 60, y * 11 % 256, 255))
    for y in range(top, size - bottom):
        for x in range(left, size - right):
            if ((x - left) // 2 + (y - top) // 2) % 2 == 0:
                image.putpixel((x, y), (20, 220, 40, 255))
            else:
                image.putpixel((x, y), (30, 40, 230, 255))
    return image


def _solid_panel(fill: tuple[int, int, int, int], size: int = 16) -> Image.Image:
    image = Image.new("RGBA", (size, size), fill)
    ImageDraw.Draw(image).rectangle((0, 0, size - 1, size - 1), outline=(210, 210, 200, 255), width=2)
    return image


def _default_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def test_nine_slice_tiled_tiles_edges_and_center():
    inset = (5, 3, 4, 6)
    left, top, right, bottom = inset
    source = _pattern_panel(inset=inset)
    centre_w = source.width - left - right
    centre_h = source.height - top - bottom
    width, height = 41, 29

    out = nine_slice_tiled(source, width, height, inset, nearest=True)

    assert out.size == (width, height)
    assert out.getpixel((0, 0)) == source.getpixel((0, 0))
    assert out.getpixel((width - 1, 0)) == source.getpixel((source.width - 1, 0))
    assert out.getpixel((0, height - 1)) == source.getpixel((0, source.height - 1))
    assert out.getpixel((width - 1, height - 1)) == source.getpixel((source.width - 1, source.height - 1))

    for x in range(left, width - right):
        sx = left + (x - left) % centre_w
        assert out.getpixel((x, 0)) == source.getpixel((sx, 0))
        assert out.getpixel((x, height - 1)) == source.getpixel((sx, source.height - 1))
    for y in range(top, height - bottom):
        sy = top + (y - top) % centre_h
        assert out.getpixel((0, y)) == source.getpixel((0, sy))
        assert out.getpixel((width - 1, y)) == source.getpixel((source.width - 1, sy))

    for y in range(top, height - bottom):
        sy = top + (y - top) % centre_h
        for x in range(left, width - right):
            sx = left + (x - left) % centre_w
            assert out.getpixel((x, y)) == source.getpixel((sx, sy))

    # The centre must not overwrite the bottom edge when top != bottom.
    assert out.getpixel((left + 1, height - bottom)) == source.getpixel((left + 1, source.height - bottom))


def test_nine_slice_tiled_solid_fill_keeps_well_flat():
    inset = (5, 3, 4, 6)
    left, top, right, bottom = inset
    source = _pattern_panel(inset=inset)
    fill = (9, 8, 7, 255)

    out = nine_slice_tiled(source, 41, 29, inset, nearest=True, fill=fill)

    for y in range(top, 29 - bottom):
        for x in range(left, 41 - right):
            assert out.getpixel((x, y)) == fill
    assert out.getpixel((0, 0)) == source.getpixel((0, 0))
    assert out.getpixel((20, 0)) == source.getpixel((left + (20 - left) % (source.width - left - right), 0))


def test_playfield_world_reserves_default_edge_docks():
    left, top, right, bottom = playfield_world(1920, 1080)

    assert HUD_DOCKS["margin"] > 0
    assert (left, top) == (HUD_DOCKS["left"], HUD_DOCKS["top"])
    assert right == 1920 - HUD_DOCKS["right"]
    assert bottom == 1080 - HUD_DOCKS["bottom"]
    assert 0 < left < right < 1920
    assert 0 < top < bottom < 1080


def test_playfield_world_honours_custom_docks_and_output_scale():
    docks = {"margin": 8, "top": 40, "right": 60, "bottom": 50, "left": 30}

    assert playfield_world(400, 300, docks) == (30, 40, 340, 250)
    assert playfield_world(640, 360, HUD_DOCKS, output_size=(1920, 1080)) == (11, 43, 520, 291)


def test_sample_well_color_returns_opaque_median():
    source = Image.new("RGBA", (16, 16), (60, 90, 120, 255))

    assert sample_well_color(source, 4) == (60, 90, 120, 240)


def test_wrap_text_keeps_words_and_handles_empty_text():
    font = _default_font(14)

    lines = wrap_text("the quick brown fox jumps over the lazy dog", font, 60)

    assert len(lines) >= 2
    assert " ".join(lines) == "the quick brown fox jumps over the lazy dog"
    assert wrap_text("", font, 60) == [""]


def _render_hud(
    fill: tuple[int, int, int, int],
    *,
    text_color: tuple[int, int, int, int] | None = None,
    prompts: list[str] | None = None,
) -> tuple[Image.Image, Image.Image, list[tuple]]:
    canvas = Image.new("RGBA", (320, 200), (20, 24, 30, 255))
    panel = _solid_panel(fill)
    hud = {
        "title": "CIDERLATCH",
        "meta_lines": ["Day 3"],
        "dialogue_speaker": "Merchant",
        "dialogue_text": "Fresh turnips today, traveller.",
        "panel_slug": "ui/widget/panel_light",
        "well_fill": fill,
        "panel_inset": 4,
    }
    if text_color is not None:
        hud["text_color"] = text_color
    if prompts is not None:
        hud["prompts"] = prompts

    calls: list[tuple] = []

    def load_image(slug: str) -> Image.Image:
        calls.append(("image", slug))
        return panel.copy()

    def load_font(role: str, size: int) -> ImageFont.ImageFont:
        calls.append(("font", role, size))
        return _default_font(size)

    out = draw_hud(
        canvas,
        hud,
        style="pixel_32",
        docks={"margin": 8, "top": 28, "right": 8, "bottom": 60, "left": 8},
        load_image=load_image,
        load_font=load_font,
    )
    return out, panel, calls


def test_draw_hud_renders_text_into_a_docked_panel():
    out, _panel, calls = _render_hud((250, 250, 245, 255))

    assert out.size == (320, 200)
    assert ("image", "pixel_32/ui/widget/panel_light") in calls

    playfield = playfield_world(
        320, 200, {"margin": 8, "top": 28, "right": 8, "bottom": 60, "left": 8}
    )
    fill_ys = [y for y in range(200) for x in range(320) if out.getpixel((x, y)) == (250, 250, 245, 255)]
    assert fill_ys
    assert min(fill_ys) >= playfield[3]

    dark_text = sum(
        1
        for y in range(playfield[3] + 8, 192)
        for x in range(45, 275)
        if all(channel < 100 for channel in out.getpixel((x, y))[:3])
    )
    assert dark_text > 20

    title_pixels = sum(
        1 for y in range(playfield[1]) for x in range(320) if sum(out.getpixel((x, y))[:3]) > 500
    )
    assert title_pixels > 20


def test_draw_hud_light_well_keeps_text_dark():
    out, _panel, _calls = _render_hud((250, 250, 245, 255))

    dark_text = sum(
        1
        for y in range(148, 190)
        for x in range(54, 268)
        if all(channel < 100 for channel in out.getpixel((x, y))[:3])
    )
    assert dark_text > 20


def test_draw_hud_dark_well_keeps_text_light():
    out, _panel, _calls = _render_hud((18, 18, 22, 255))

    light_text = sum(
        1
        for y in range(148, 190)
        for x in range(54, 268)
        if all(channel > 200 for channel in out.getpixel((x, y))[:3])
    )
    assert light_text > 20


def test_draw_hud_scrim_stays_in_the_bottom_dock():
    out, _panel, _calls = _render_hud((250, 250, 245, 255))

    assert out.getpixel((5, 100)) == (20, 24, 30, 255)
    assert sum(out.getpixel((5, 195))[:3]) < 74


def test_draw_hud_draws_prompts_as_keycaps():
    plain, _panel, _calls = _render_hud((250, 250, 245, 255))
    prompted, _panel2, _calls2 = _render_hud(
        (250, 250, 245, 255), prompts=["E Talk", "Esc Close"]
    )

    region = (220, 160, 316, 196)
    changed = sum(
        1
        for y in range(region[1], region[3])
        for x in range(region[0], region[2])
        if plain.getpixel((x, y)) != prompted.getpixel((x, y))
    )
    assert changed > 30
