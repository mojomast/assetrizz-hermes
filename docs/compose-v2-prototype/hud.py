"""Screen-space HUD docks and before/after contact sheets."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from assets import (
    FONT_CUSTOM,
    font,
    fonts_for,
    nine_slice_tiled,
    open_slug,
    sample_well_color,
    scale_img,
)


def _text(draw, xy, text, font_, fill, stroke=None, stroke_w=2, anchor="lt"):
    kw = {"font": font_, "fill": fill, "anchor": anchor}
    if stroke is not None:
        kw["stroke_width"] = stroke_w
        kw["stroke_fill"] = stroke
    draw.text(xy, text, **kw)


def _wrap(text: str, font_, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    dummy = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    for word in words:
        trial = word if not cur else f"{cur} {word}"
        if dummy.textlength(trial, font=font_) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def _shadow(panel: Image.Image, radius: int = 8, offset=(0, 4), alpha: int = 140) -> Image.Image:
    canvas = Image.new("RGBA", (panel.width + radius * 4, panel.height + radius * 4), (0, 0, 0, 0))
    mask = panel.split()[-1]
    sh = Image.new("RGBA", panel.size, (0, 0, 0, alpha))
    sh.putalpha(mask.point(lambda p: min(255, int(p * alpha / 255))))
    canvas.paste(sh, (radius * 2 + offset[0], radius * 2 + offset[1]), sh)
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=radius))
    canvas.alpha_composite(panel, (radius * 2, radius * 2))
    return canvas


def _paste(base: Image.Image, sprite: Image.Image, xy: tuple[int, int]) -> None:
    x, y = xy
    if x < 0 or y < 0 or x >= base.width or y >= base.height:
        return
    if x + sprite.width <= 0 or y + sprite.height <= 0:
        return
    base.alpha_composite(sprite, (x, y))


def _fit_icon(im: Image.Image, box: int, nearest: bool) -> Image.Image:
    bb = im.split()[-1].getbbox()
    if bb:
        im = im.crop(bb)
    scale = min(box / im.width, box / im.height)
    return scale_img(im, scale, nearest)


def _keycap(label: str, font_, fg=(240, 240, 245, 255), bg=(20, 20, 28, 230), border=(220, 220, 230, 255), pad=8) -> Image.Image:
    dummy = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    tw = int(dummy.textlength(label, font=font_))
    try:
        bbox = dummy.textbbox((0, 0), label, font=font_)
        th = bbox[3] - bbox[1]
    except Exception:
        th = 16
    w, h = tw + pad * 2 + 4, th + pad * 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=6, fill=bg, outline=border, width=2)
    d.text(((w - tw) // 2, (h - th) // 2 - 1), label, font=font_, fill=fg)
    return im


def make_bar(style: str, fill_name: str, width: int, height: int, fraction: float, nearest: bool) -> Image.Image:
    track = open_slug(f"{style}/ui/widget/bar_track_plain")
    fill = open_slug(f"{style}/ui/widget/{fill_name}")
    inset_t = max(6, min(track.size) // 4)
    inset_f = max(6, min(fill.size) // 4)
    track_s = nine_slice_tiled(track, width, height, inset_t, nearest=nearest)
    inner_w = max(8, int((width - 8) * max(0.0, min(1.0, fraction))))
    inner_h = max(6, height - 8)
    fill_s = nine_slice_tiled(fill, inner_w, inner_h, inset_f, nearest=nearest)
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.alpha_composite(track_s, (0, 0))
    out.alpha_composite(fill_s, (4, (height - inner_h) // 2))
    return out


def framed_panel(style: str, name: str, width: int, height: int, nearest: bool, inset: int | None = None) -> Image.Image:
    src = open_slug(f"{style}/ui/widget/{name}")
    if inset is None:
        inset = 22 if min(src.size) <= 80 else 56
    fill = sample_well_color(src, inset)
    return nine_slice_tiled(src, width, height, inset, nearest=nearest, fill=fill)


def draw_hud(canvas: Image.Image, compiled: dict[str, Any]) -> None:
    hud = compiled.get("hud") or {}
    tmpl = compiled.get("template") or {}
    style = tmpl.get("style") or compiled["meta"]["style"]
    nearest = bool(tmpl.get("nearest"))
    title_f, ui_f, sm_f = fonts_for(style)
    W, H = canvas.size
    docks = {"margin": 32, "top": 128, "right": 360, "bottom": 208, "left": 32}
    for k in ("margin", "top", "right", "bottom", "left"):
        if k in hud:
            docks[k] = hud[k]
    margin = int(docks["margin"])
    title_color = tuple(hud.get("title_color") or ((255, 244, 196, 255) if nearest else (220, 236, 245, 255)))
    text_color = tuple(hud.get("text_color") or ((40, 28, 18, 255) if nearest else (230, 236, 240, 255)))
    muted = tuple(hud.get("muted_color") or ((70, 52, 32, 255) if nearest else (160, 176, 190, 255)))
    stroke = hud.get("stroke")
    if stroke is None:
        stroke = (255, 250, 230, 180) if nearest else (8, 12, 18, 210)
    else:
        stroke = tuple(stroke) if stroke else None

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    scrim_h = int(docks["bottom"])
    scrim = Image.new("RGBA", (W, scrim_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for i in range(scrim_h):
        a = int(160 * (i / max(1, scrim_h - 1)) ** 1.2)
        sd.line((0, i, W, i), fill=(6, 8, 12, a))
    layer.alpha_composite(scrim, (0, H - scrim_h))

    left = margin
    top = 24
    title = hud.get("title") or compiled["meta"].get("title") or ""
    if title:
        _text(d, (left, top), title, title_f, title_color, stroke, 3 if stroke else 0, anchor="lt")
        tb = d.textbbox((left, top), title, font=title_f, stroke_width=3 if stroke else 0)
        y = tb[3] + 8
    else:
        y = top
    for line in hud.get("meta_lines") or []:
        _text(d, (left, y), line, sm_f, muted, stroke, 2, anchor="lt")
        lb = d.textbbox((left, y), line, font=sm_f, stroke_width=2)
        y = lb[3] + 4
    y += 6
    bar_w, bar_h = (260, 26) if nearest else (300, 28)
    for bar in hud.get("bars") or []:
        label = bar["label"]
        _text(d, (left, y + bar_h // 2), label, sm_f, text_color, stroke, 2, anchor="lm")
        lw = int(d.textlength(label, font=sm_f))
        bx = left + lw + 12
        bar_im = make_bar(style, bar["fill"], bar_w, bar_h, bar["frac"], nearest)
        _paste(layer, bar_im, (bx, y))
        _text(d, (bx + bar_w + 10, y + bar_h // 2), bar["value"], sm_f, text_color, stroke, 2, anchor="lm")
        y += bar_h + 8
    if hud.get("currency"):
        cy = y + 4
        icon_slug = hud.get("currency_icon")
        try:
            if icon_slug:
                kind, name = icon_slug.split("/", 1)
                coin = _fit_icon(open_slug(f"{style}/icons/{kind}/{name}_plain"), 36, nearest)
                _paste(layer, coin, (left, cy - 4))
                _text(d, (left + coin.width + 8, cy + coin.height // 2), hud["currency"], ui_f, title_color, stroke, 2, anchor="lm")
            else:
                _text(d, (left, cy), hud["currency"], ui_f, title_color, stroke, 2, anchor="lt")
        except Exception as exc:
            print("currency icon failed:", exc)
            _text(d, (left, cy), str(hud["currency"]), ui_f, title_color, stroke, 2, anchor="lt")

    if hud.get("minimap", True):
        mm = open_slug(f"{style}/ui/widget/minimap_frame_plain")
        bb = mm.split()[-1].getbbox()
        if bb:
            mm = mm.crop(bb)
        target = 180 if nearest else 200
        resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
        mm_s = mm.resize((target, target), resample)
        mx, my = W - target - margin, 24
        sh = _shadow(mm_s, radius=6, offset=(0, 3), alpha=160)
        _paste(layer, sh, (mx - 12, my - 12))
        pd = ImageDraw.Draw(mm_s)
        if hud.get("radar"):
            cx, cy = mm_s.width // 2, mm_s.height // 2
            inset = 28
            for rad in (18, 36, 54):
                pd.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=(80, 200, 220, 110), width=1)
            pd.line((cx, inset, cx, target - inset), fill=(80, 200, 220, 70), width=1)
            pd.line((inset, cy, target - inset, cy), fill=(80, 200, 220, 70), width=1)
            pd.polygon([(cx, cy - 7), (cx + 6, cy + 5), (cx - 6, cy + 5)], fill=(255, 230, 90, 255), outline=(8, 14, 18, 255))
            for bx, by in ((18, -12), (-40, 8), (36, 22), (-22, 28)):
                pd.ellipse((cx + bx - 3, cy + by - 3, cx + bx + 3, cy + by + 3), fill=(255, 80, 90, 255))
        else:
            cx, cy = mm_s.width // 2, int(mm_s.height * 0.58)
            pd.polygon([(cx, cy - 8), (cx + 7, cy + 6), (cx - 7, cy + 6)], fill=(255, 230, 90, 255), outline=(20, 16, 8, 255))
        _paste(layer, mm_s, (mx, my))
        quest_top = my + target + 16
    else:
        quest_top = 24

    if hud.get("quest_title"):
        qw, qh = 320, 180
        qx, qy = W - qw - margin, quest_top
        panel_name = hud.get("panel_widget") or ("panel_light" if nearest else "panel_dark")
        panel = framed_panel(style, panel_name, qw, qh, nearest)
        sh = _shadow(panel, radius=8, offset=(0, 4), alpha=150)
        _paste(layer, sh, (qx - 16, qy - 16))
        _paste(layer, panel, (qx, qy))
        pd = ImageDraw.Draw(layer)
        tx, ty = qx + 24, qy + 20
        _text(pd, (tx, ty), hud["quest_title"], ui_f, title_color, stroke, 2, anchor="lt")
        tb = pd.textbbox((tx, ty), hud["quest_title"], font=ui_f)
        ty = tb[3] + 10
        for line in hud.get("quest_lines") or []:
            for wrapped in _wrap("\u25b8 " + line, sm_f, qw - 48):
                _text(pd, (tx, ty), wrapped, sm_f, text_color, stroke, 1, anchor="lt")
                lb = pd.textbbox((tx, ty), wrapped, font=sm_f)
                ty = lb[3] + 6

    slots = hud.get("hotbar") or []
    dialogue_h = 120
    dy = H - margin - dialogue_h
    slot_size = 64
    gap = 6
    if slots:
        n = len(slots)
        total = n * slot_size + (n - 1) * gap
        hx = (W - total) // 2
        hy = dy - 8 - slot_size
        empty = open_slug(f"{style}/ui/widget/item_slot_empty")
        selected = open_slug(f"{style}/ui/widget/item_slot_selected")

        def _slot_img(src, ss):
            bb = src.split()[-1].getbbox()
            if bb:
                src = src.crop(bb)
            resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
            return src.resize((ss, ss), resample)

        empty_s = _slot_img(empty, slot_size)
        selected_s = _slot_img(selected, slot_size)
        sel = int(hud.get("hotbar_selected") or 0)
        for i, slug in enumerate(slots):
            slot = selected_s if i == sel else empty_s
            sx, sy = hx + i * (slot_size + gap), hy
            _paste(layer, slot, (sx, sy))
            if slug:
                try:
                    ic = _fit_icon(open_slug(slug), int(slot_size * 0.62), nearest)
                    _paste(layer, ic, (sx + (slot_size - ic.width) // 2, sy + (slot_size - ic.height) // 2))
                except Exception as exc:
                    print("hotbar icon failed", slug, exc)
            _text(ImageDraw.Draw(layer), (sx + 8, sy + 6), str((i + 1) % 10), sm_f, muted, stroke, 1, anchor="lt")

    if hud.get("dialogue_text"):
        dw, dh = 1100, dialogue_h
        dx = (W - dw) // 2
        widget = hud.get("dialogue_widget") or "dialogue_box_plain"
        inset = 22 if nearest else 56
        box = framed_panel(style, widget, dw, dh, nearest, inset=inset)
        sh = _shadow(box, radius=10, offset=(0, 5), alpha=160)
        _paste(layer, sh, (dx - 20, dy - 20))
        _paste(layer, box, (dx, dy))
        pd = ImageDraw.Draw(layer)
        tx, ty = dx + 36, dy + 18
        if hud.get("dialogue_speaker"):
            _text(pd, (tx, ty), hud["dialogue_speaker"], ui_f, title_color, stroke, 2, anchor="lt")
            tb = pd.textbbox((tx, ty), hud["dialogue_speaker"], font=ui_f)
            ty = tb[3] + 8
        for line in _wrap(hud["dialogue_text"], ui_f, dw - 200):
            _text(pd, (tx, ty), line, ui_f, text_color, stroke, 1, anchor="lt")
            lb = pd.textbbox((tx, ty), line, font=ui_f)
            ty = lb[3] + 4
        px = dx + dw - 24
        py = dy + dh - 18
        for label in reversed(hud.get("prompts") or []):
            parts = label.split(None, 1)
            if len(parts) == 2 and len(parts[0]) <= 4:
                cap = _keycap(parts[0], sm_f)
                cw = int(ImageDraw.Draw(layer).textlength(parts[1], font=sm_f))
                total_w = cap.width + 8 + cw
                px = px - total_w
                _paste(layer, cap, (px, py - cap.height))
                _text(pd, (px + cap.width + 8, py - cap.height // 2), parts[1], sm_f, text_color, stroke, 1, anchor="lm")
                px -= 22
            else:
                cap = _keycap(label, sm_f)
                px = px - cap.width
                _paste(layer, cap, (px, py - cap.height))
                px -= 16

    canvas.alpha_composite(layer)


def side_by_side(before: Path, after: Path, dest: Path, *, title: str) -> Path:
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    h = 540

    def fit(im):
        r = h / im.height
        return im.resize((int(im.width * r), h), Image.Resampling.LANCZOS)

    a, b = fit(a), fit(b)
    gap, pad, header, footer = 28, 36, 64, 28
    W = pad * 2 + a.width + gap + b.width
    H = pad + header + h + footer
    canvas = Image.new("RGB", (W, H), (22, 20, 18))
    d = ImageDraw.Draw(canvas)
    title_f = font(FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Bold.ttf", 28)
    cap_f = font(FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Semibold.ttf", 16)
    muted, cream = (168, 160, 148), (236, 228, 214)
    d.text((pad, 20), title, font=title_f, fill=cream)
    ax, ay = pad, pad + header
    bx, by = pad + a.width + gap, pad + header
    d.rectangle((ax - 1, ay - 1, ax + a.width, ay + a.height), outline=(48, 44, 40))
    d.rectangle((bx - 1, by - 1, bx + b.width, by + b.height), outline=(48, 44, 40))
    canvas.paste(a, (ax, ay))
    canvas.paste(b, (bx, by))
    d.text((ax, ay + h + 8), "Before", font=cap_f, fill=muted)
    d.text((bx, by + h + 8), "After", font=cap_f, fill=muted)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, format="JPEG", quality=90, optimize=True)
    return dest


def contact_sheet(pairs: list[tuple[str, Path, Path]], dest: Path) -> Path:
    h = 400

    def fit(im):
        r = h / im.height
        return im.resize((int(im.width * r), h), Image.Resampling.LANCZOS)

    rows = [(title, fit(Image.open(before).convert("RGB")), fit(Image.open(after).convert("RGB")))
            for title, before, after in pairs]
    gap, pad, header, row_gap, label_h = 24, 40, 72, 48, 26
    col_w = rows[0][1].width
    W = pad * 2 + col_w + gap + col_w
    H = pad + header + len(rows) * (h + label_h + row_gap) - row_gap + pad
    canvas = Image.new("RGB", (W, H), (22, 20, 18))
    d = ImageDraw.Draw(canvas)
    title_f = font(FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Bold.ttf", 30)
    cap_f = font(FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Semibold.ttf", 15)
    small = font(FONT_CUSTOM / "Source Sans Pro" / "SourceSansPro-Regular.ttf", 14)
    cream, muted = (236, 228, 214), (168, 160, 148)
    d.text((pad, 22), "Scene composition, before and after", font=title_f, fill=cream)
    d.text((pad, 54), "Same assets. Named layers, a grid ground plane, y-sort, reserved HUD docks.", font=small, fill=muted)
    y = pad + header
    for title, a, b in rows:
        ax, bx = pad, pad + a.width + gap
        d.rectangle((ax - 1, y - 1, ax + a.width, y + a.height), outline=(48, 44, 40))
        d.rectangle((bx - 1, y - 1, bx + b.width, y + b.height), outline=(48, 44, 40))
        canvas.paste(a, (ax, y))
        canvas.paste(b, (bx, y))
        d.text((ax, y + h + 6), f"{title}  -  before", font=cap_f, fill=muted)
        d.text((bx, y + h + 6), f"{title}  -  after", font=cap_f, fill=muted)
        y += h + label_h + row_gap
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, format="JPEG", quality=90, optimize=True)
    return dest
