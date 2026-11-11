"""Screen-space HUD docks, tiled nine-slice panels, and HUD text.

The HUD is drawn after the world render, in screen space. Docks reserve the
screen edges; the remaining rectangle is the world playfield. Panels tile
their edges and centre instead of stretching them, so nine-slice art does not
smear, and an optional solid well keeps text readable.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HUD_DOCKS: dict[str, int] = {
    "margin": 32,
    "top": 128,
    "right": 360,
    "bottom": 208,
    "left": 32,
}

_DOCK_KEYS = ("margin", "top", "right", "bottom", "left")


def _dock_values(docks: Mapping[str, int] | None) -> dict[str, int]:
    values = dict(HUD_DOCKS)
    if docks:
        for key in _DOCK_KEYS:
            if key in docks:
                values[key] = int(docks[key])
    return values


def playfield_world(
    width: int,
    height: int,
    docks: Mapping[str, int] | None = None,
    *,
    output_size: tuple[int, int] | None = None,
) -> tuple[int, int, int, int]:
    """Return the world playfield as ``(left, top, right, bottom)``.

    ``width`` and ``height`` are in world/compose pixels. Dock reservations are
    in that same space unless ``output_size`` is given, in which case they are
    scaled down from the output resolution (for example 1920x1080).
    """
    try:
        width, height = int(width), int(height)
    except (TypeError, ValueError) as exc:
        raise ValueError("playfield size must be integer pixels") from exc
    if width <= 0 or height <= 0:
        raise ValueError("playfield size must be positive")

    values = _dock_values(docks)
    if output_size is None:
        scale_x = scale_y = 1.0
    else:
        try:
            out_w, out_h = int(output_size[0]), int(output_size[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError("output_size must be a (width, height) pair") from exc
        if out_w <= 0 or out_h <= 0:
            raise ValueError("output_size must be positive")
        scale_x, scale_y = width / out_w, height / out_h

    left = min(max(0, round(values["left"] * scale_x)), width - 1)
    top = min(max(0, round(values["top"] * scale_y)), height - 1)
    right = max(left + 1, width - round(values["right"] * scale_x))
    bottom = max(top + 1, height - round(values["bottom"] * scale_y))
    return left, top, min(right, width), min(bottom, height)


def _rgba(value: Any, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("#") and len(text) in (4, 7):
            raw = text[1:]
            if len(raw) == 3:
                raw = "".join(ch * 2 for ch in raw)
            return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 255)
        raise ValueError("HUD colors must be #RGB, #RRGGBB, or 3-4 channel sequences")
    try:
        channels = tuple(int(channel) for channel in value)
    except (TypeError, ValueError) as exc:
        raise ValueError("HUD colors must be #RGB, #RRGGBB, or 3-4 channel sequences") from exc
    if len(channels) == 3:
        return (channels[0], channels[1], channels[2], 255)
    if len(channels) == 4:
        return (channels[0], channels[1], channels[2], channels[3])
    raise ValueError("HUD colors must have 3 or 4 channels")


def _luminance(color: Sequence[int]) -> float:
    return 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]


def _readable_text_color(fill: Sequence[int]) -> tuple[int, int, int, int]:
    if _luminance(fill) >= 140:
        return (18, 18, 20, 255)
    return (240, 240, 240, 255)


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """Wrap on word boundaries without dropping or splitting words."""
    words = str(text).split()
    if not words:
        return [""]
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if not current or measure(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def draw_shadow_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    *,
    shadow: tuple[int, int, int, int] = (0, 0, 0, 170),
    offset: tuple[int, int] = (1, 1),
    anchor: str = "lt",
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int, int] | None = None,
) -> None:
    """Draw text with a soft offset shadow, then the readable foreground."""
    draw.text(
        (xy[0] + offset[0], xy[1] + offset[1]),
        text,
        font=font,
        fill=shadow,
        anchor=anchor,
    )
    draw.text(
        xy,
        text,
        font=font,
        fill=fill,
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )


def sample_well_color(image: Image.Image, inset: int) -> tuple[int, int, int, int]:
    """Return the median opaque colour inside a panel's well area."""
    image = image.convert("RGBA")
    width, height = image.size
    pad = max(0, int(inset))
    left = min(pad, max(0, width - 1))
    top = min(pad, max(0, height - 1))
    right = min(width, max(left + 1, width - pad))
    bottom = min(height, max(top + 1, height - pad))
    crop = image.crop((left, top, right, bottom))
    raw = crop.tobytes()
    pixels = [
        (raw[index], raw[index + 1], raw[index + 2], raw[index + 3])
        for index in range(0, len(raw), 4)
        if raw[index + 3] >= 200
    ]
    if not pixels:
        return (28, 24, 22, 240)
    channels = list(zip(*pixels))
    middle = len(pixels) // 2
    return (
        sorted(channels[0])[middle],
        sorted(channels[1])[middle],
        sorted(channels[2])[middle],
        240,
    )


def nine_slice_tiled(
    image: Image.Image,
    width: int,
    height: int,
    inset: int | tuple[int, int, int, int],
    *,
    nearest: bool = False,
    fill: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    """Nine-slice a panel by tiling its edges and centre, never stretching."""
    source = image.convert("RGBA")
    source_w, source_h = source.size
    if source_w < 3 or source_h < 3:
        raise ValueError("nine-slice source must be at least 3x3 pixels")

    if isinstance(inset, int):
        left = top = right = bottom = int(inset)
    else:
        values = tuple(int(value) for value in inset)
        if len(values) != 4:
            raise ValueError("inset must be an int or a (left, top, right, bottom) tuple")
        left, top, right, bottom = values

    left = max(1, min(left, source_w // 2 - 1))
    right = max(1, min(right, source_w - left - 1))
    top = max(1, min(top, source_h // 2 - 1))
    bottom = max(1, min(bottom, source_h - top - 1))

    width = max(int(width), left + right + 1)
    height = max(int(height), top + bottom + 1)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS

    def region(piece: Image.Image, dest_w: int, dest_h: int, mode: str) -> Image.Image:
        if dest_w <= 0 or dest_h <= 0:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        if mode == "corner":
            if piece.size != (dest_w, dest_h):
                piece = piece.resize((dest_w, dest_h), resample)
            return piece
        canvas = Image.new("RGBA", (dest_w, dest_h), (0, 0, 0, 0))
        piece_w, piece_h = piece.size
        if mode == "edge_h":
            if piece_h != dest_h:
                piece = piece.resize((max(1, piece_w), dest_h), resample)
                piece_w, piece_h = piece.size
            x = 0
            while x < dest_w:
                canvas.paste(piece, (x, 0), piece)
                x += piece_w
            return canvas
        if mode == "edge_v":
            if piece_w != dest_w:
                piece = piece.resize((dest_w, max(1, piece_h)), resample)
                piece_w, piece_h = piece.size
            y = 0
            while y < dest_h:
                canvas.paste(piece, (0, y), piece)
                y += piece_h
            return canvas
        y = 0
        while y < dest_h:
            x = 0
            while x < dest_w:
                canvas.paste(piece, (x, y), piece)
                x += piece_w
            y += piece_h
        return canvas

    corners = (
        ((0, 0, left, top), (0, 0)),
        ((source_w - right, 0, source_w, top), (width - right, 0)),
        ((0, source_h - bottom, left, source_h), (0, height - bottom)),
        (
            (source_w - right, source_h - bottom, source_w, source_h),
            (width - right, height - bottom),
        ),
    )
    for (x0, y0, x1, y1), (dest_x, dest_y) in corners:
        piece = region(source.crop((x0, y0, x1, y1)), x1 - x0, y1 - y0, "corner")
        out.paste(piece, (dest_x, dest_y), piece)

    top_piece = region(
        source.crop((left, 0, source_w - right, top)),
        width - left - right,
        top,
        "edge_h",
    )
    out.paste(top_piece, (left, 0), top_piece)
    bottom_piece = region(
        source.crop((left, source_h - bottom, source_w - right, source_h)),
        width - left - right,
        bottom,
        "edge_h",
    )
    out.paste(bottom_piece, (left, height - bottom), bottom_piece)
    left_piece = region(
        source.crop((0, top, left, source_h - bottom)),
        left,
        height - top - bottom,
        "edge_v",
    )
    out.paste(left_piece, (0, top), left_piece)
    right_piece = region(
        source.crop((source_w - right, top, source_w, source_h - bottom)),
        right,
        height - top - bottom,
        "edge_v",
    )
    out.paste(right_piece, (width - right, top), right_piece)

    well_w = max(1, width - left - right)
    well_h = max(1, height - top - bottom)
    if fill is not None:
        well = Image.new("RGBA", (well_w, well_h), _rgba(fill, (0, 0, 0, 0)))
        out.paste(well, (left, top))
    else:
        centre = region(
            source.crop((left, top, source_w - right, source_h - bottom)),
            well_w,
            well_h,
            "tile",
        )
        out.paste(centre, (left, top), centre)
    return out


def _style_slug(style: str, slug: str) -> str:
    text = str(slug).strip().strip("/")
    if not text:
        text = "ui/widget/panel_dark"
    if style and not text.startswith(f"{style}/"):
        text = f"{style}/{text}"
    return text


def _default_image(slug: str) -> Image.Image:
    from assetrizz_plugin.library import resolve_asset

    asset = resolve_asset(slug=slug)
    with Image.open(asset["file"]) as image:
        return image.convert("RGBA")


def _default_font(_role: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _line_height(font: ImageFont.ImageFont) -> int:
    bbox = font.getbbox("Ag")
    height = max(1, bbox[3] - bbox[1])
    return height + max(1, height // 5)


def _panel_shadow(
    panel: Image.Image,
    *,
    radius: int = 6,
    offset: tuple[int, int] = (0, 4),
    alpha: int = 130,
) -> Image.Image:
    pad = radius * 3
    shadow = Image.new("RGBA", (panel.width + pad * 2, panel.height + pad * 2), (0, 0, 0, 0))
    shape = Image.new("RGBA", panel.size, (0, 0, 0, alpha))
    shadow.paste(shape, (pad + offset[0], pad + offset[1]), shape)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius))
    shadow.alpha_composite(panel, (pad, pad))
    return shadow


def _keycap(label: str, font: ImageFont.ImageFont) -> Image.Image:
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = measure.textbbox((0, 0), label, font=font)
    text_w = max(1, bbox[2] - bbox[0])
    text_h = max(1, bbox[3] - bbox[1])
    pad = 6
    image = Image.new("RGBA", (text_w + pad * 2, text_h + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, image.width - 1, image.height - 1),
        radius=5,
        fill=(20, 20, 28, 230),
        outline=(220, 220, 230, 255),
        width=1,
    )
    draw.text((pad - bbox[0], pad - bbox[1]), label, font=font, fill=(240, 240, 245, 255))
    return image


def draw_hud(
    canvas: Image.Image,
    hud: Mapping[str, Any],
    *,
    style: str = "",
    docks: Mapping[str, int] | None = None,
    load_image: Callable[[str], Image.Image] | None = None,
    load_font: Callable[[str, int], ImageFont.ImageFont] | None = None,
    nearest: bool = False,
) -> Image.Image:
    """Paint docked HUD panels and text onto an RGBA canvas.

    ``load_image`` and ``load_font`` are injectable so callers (and tests) can
    supply library panels or synthetic images without touching production
    files. The default image loader resolves a style-scoped widget slug through
    the plugin library.
    """
    if not isinstance(canvas, Image.Image):
        raise TypeError("draw_hud needs a Pillow image")

    spec = dict(hud or {})
    values = _dock_values(docks)
    margin = max(0, values["margin"])
    top_dock = max(0, values["top"])
    bottom_dock = max(0, values["bottom"])
    width, height = canvas.size

    image_loader = load_image or _default_image
    font_loader = load_font or _default_font

    title_size = max(10, int(spec.get("title_size") or 22))
    if top_dock:
        title_size = max(8, min(title_size, top_dock - 8))
    body_size = max(9, int(spec.get("body_size") or 16))
    small_size = max(8, int(spec.get("small_size") or 12))
    title_font = font_loader("title", title_size)
    body_font = font_loader("body", body_size)
    small_font = font_loader("small", small_size)

    title_color = _rgba(
        spec.get("title_color"),
        (255, 244, 196, 255) if nearest else (220, 236, 245, 255),
    )
    muted_color = _rgba(
        spec.get("muted_color"),
        (70, 52, 32, 255) if nearest else (160, 176, 190, 255),
    )
    raw_stroke = spec.get("stroke")
    if raw_stroke is False:
        stroke_color = None
    elif raw_stroke is None:
        stroke_color = (255, 250, 230, 180) if nearest else (8, 12, 18, 210)
    else:
        stroke_color = _rgba(raw_stroke, (8, 12, 18, 210))
    stroke_width = 2 if stroke_color else 0

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if spec.get("scrim", True) and bottom_dock:
        scrim_h = min(height, bottom_dock)
        scrim = Image.new("RGBA", (width, scrim_h), (0, 0, 0, 0))
        scrim_draw = ImageDraw.Draw(scrim)
        for row in range(scrim_h):
            alpha = int(110 * (row / max(1, scrim_h - 1)) ** 1.2)
            scrim_draw.line((0, row, width, row), fill=(6, 8, 12, alpha))
        layer.alpha_composite(scrim, (0, height - scrim_h))

    title = str(spec.get("title") or "")
    text_y = max(4, margin // 2)
    if title:
        draw_shadow_text(
            draw,
            (margin, text_y),
            title,
            title_font,
            title_color,
            anchor="lt",
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
        title_box = draw.textbbox(
            (margin, text_y),
            title,
            font=title_font,
            stroke_width=stroke_width,
        )
        text_y = title_box[3] + 6

    for line in spec.get("meta_lines") or []:
        draw_shadow_text(
            draw,
            (margin, text_y),
            str(line),
            small_font,
            muted_color,
            anchor="lt",
            stroke_width=1 if stroke_color else 0,
            stroke_fill=stroke_color,
        )
        line_box = draw.textbbox(
            (margin, text_y),
            str(line),
            font=small_font,
            stroke_width=1 if stroke_color else 0,
        )
        text_y = line_box[3] + 3

    dialogue_text = str(spec.get("dialogue_text") or "")
    if dialogue_text and bottom_dock and width > 0:
        panel_h = int(spec.get("dialogue_height") or max(1, bottom_dock - margin))
        panel_h = max(1, min(panel_h, height))
        panel_w = int(spec.get("dialogue_width") or min(max(1, width - margin * 2), max(1, int(width * 0.72))))
        panel_w = max(1, min(panel_w, width))
        panel_x = (width - panel_w) // 2
        panel_y = max(0, height - bottom_dock)

        panel_slug = str(spec.get("panel_slug") or ("ui/widget/panel_light" if nearest else "ui/widget/panel_dark"))
        source = image_loader(_style_slug(style, panel_slug))
        inset = int(spec.get("panel_inset") or max(2, min(source.size) // 4))
        explicit_fill = spec.get("well_fill")
        fill = None
        if explicit_fill is not None:
            fill = _rgba(explicit_fill, (0, 0, 0, 0))
        elif spec.get("solid_well", True):
            fill = sample_well_color(source, inset)
        panel = nine_slice_tiled(
            source,
            panel_w,
            panel_h,
            inset,
            nearest=nearest,
            fill=fill,
        )
        shadow = _panel_shadow(panel, radius=6, offset=(0, 4), alpha=130)
        layer.alpha_composite(shadow, (panel_x - 18, panel_y - 14))
        layer.alpha_composite(panel, (panel_x, panel_y))
        draw = ImageDraw.Draw(layer)

        well_rgb = fill[:3] if fill is not None else sample_well_color(source, inset)[:3]
        text_color = _rgba(spec.get("text_color"), _readable_text_color(well_rgb))
        pad = max(6, margin // 2)
        text_x = panel_x + max(pad, inset + 2)
        text_y = panel_y + max(pad, inset + 2)
        max_width = max(8, panel_w - 2 * max(pad, inset + 2))
        limit_y = panel_y + panel_h - max(4, pad)

        speaker = str(spec.get("dialogue_speaker") or "")
        if speaker:
            draw_shadow_text(
                draw,
                (text_x, text_y),
                speaker,
                body_font,
                title_color,
                anchor="lt",
                stroke_width=1 if stroke_color else 0,
                stroke_fill=stroke_color,
            )
            speaker_box = draw.textbbox((text_x, text_y), speaker, font=body_font)
            text_y = speaker_box[3] + 4

        line_height = _line_height(body_font)
        for line in wrap_text(dialogue_text, body_font, max_width):
            if text_y + line_height > limit_y:
                break
            draw_shadow_text(
                draw,
                (text_x, text_y),
                line,
                body_font,
                text_color,
                anchor="lt",
                stroke_width=1 if stroke_color else 0,
                stroke_fill=stroke_color,
            )
            text_y += line_height

        prompts = [str(item) for item in spec.get("prompts") or []]
        if prompts:
            measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            cursor_x = panel_x + panel_w - pad
            cursor_y = panel_y + panel_h - pad
            for label in reversed(prompts):
                parts = label.split(None, 1)
                if len(parts) == 2 and len(parts[0]) <= 4:
                    key = _keycap(parts[0], small_font)
                    caption = parts[1]
                    caption_w = int(measure.textlength(caption, font=small_font))
                    cursor_x -= key.width + 4 + caption_w
                    if cursor_x < panel_x + pad:
                        break
                    layer.alpha_composite(key, (cursor_x, cursor_y - key.height))
                    draw_shadow_text(
                        draw,
                        (cursor_x + key.width + 4, cursor_y - key.height // 2),
                        caption,
                        small_font,
                        text_color,
                        anchor="lm",
                    )
                else:
                    key = _keycap(label, small_font)
                    cursor_x -= key.width
                    if cursor_x < panel_x + pad:
                        break
                    layer.alpha_composite(key, (cursor_x, cursor_y - key.height))
                cursor_x -= 10

    canvas.alpha_composite(layer)
    return canvas
