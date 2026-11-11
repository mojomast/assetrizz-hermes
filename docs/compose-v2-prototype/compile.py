"""Compile a declarative scene spec and lint legacy v1 scenes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bands import BANDS, CATEGORY_BAND, SKIP_SLUGS, TEMPLATES
from assets import Metrics, full_slug, metrics


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    subject: str = ""
    fix: str = ""

    def as_dict(self) -> dict[str, Any]:
        d = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.subject:
            d["subject"] = self.subject
        if self.fix:
            d["fix"] = self.fix
        return d


def target_scale(m: Metrics, tmpl: dict[str, Any], override: float | None) -> float:
    if override is not None:
        return float(override)
    if tmpl.get("scale_mode") == "native":
        return 1.0
    key = f"{m.category}/{m.subcategory}" if m.subcategory else m.category
    targets = dict(tmpl.get("target_px") or {})
    subject_t = dict(tmpl.get("target_px_subject") or {})
    target = subject_t.get(key) or targets.get(m.category)
    if not target:
        return 1.0
    vis = max(1, m.vis_h)
    return max(0.05, min(8.0, float(target) / vis))


def default_band(m: Metrics, explicit: str | None, *, flying: bool = False) -> str:
    if explicit:
        return explicit
    if flying:
        return "aerial"
    if m.category == "vehicles" and m.subcategory == "air":
        return "sky"
    if m.category == "tiles" and m.subcategory == "wall":
        return "terrain"
    return CATEGORY_BAND.get(m.category, "world")


def feet_from_topleft(m: Metrics, x: int, y: int, scale: float, flip_x: bool) -> tuple[float, float]:
    px, py = m.pivot
    if flip_x:
        px = 1.0 - px
    return (x + scale * m.width * px, y + scale * m.height * py)


def topleft_from_feet(m: Metrics, feet_x: float, feet_y: float, scale: float, flip_x: bool) -> tuple[int, int]:
    px, py = m.pivot
    if flip_x:
        px = 1.0 - px
    x = int(round(feet_x - scale * m.width * px))
    y = int(round(feet_y - scale * m.height * py))
    return x, y


def footprint(m: Metrics, feet_x: float, feet_y: float, scale: float) -> tuple[float, float, float, float]:
    vis_w = m.vis_w * scale
    if m.category in {"characters", "creatures", "enemies"}:
        fw = max(24.0, vis_w * 0.85)
        fh = max(16.0, vis_w * 0.35)
    elif m.category in {"buildings", "terrain"}:
        fw = max(32.0, vis_w * 0.70)
        fh = max(20.0, vis_w * 0.25)
    else:
        fw = max(16.0, vis_w * 0.50)
        fh = max(12.0, vis_w * 0.25)
    return (feet_x - fw / 2, feet_y - fh, feet_x + fw / 2, feet_y)


def rects_overlap(a, b, pad: float = 0.0) -> bool:
    return not (
        a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1]
    )


def merge_template(spec: dict[str, Any]) -> dict[str, Any]:
    name = spec.get("template") or ""
    base = dict(TEMPLATES.get(name) or {})
    out = dict(base)
    for k, v in spec.items():
        if k == "hud" and isinstance(v, dict) and isinstance(out.get("hud"), dict):
            hud = dict(out["hud"])
            hud.update(v)
            out["hud"] = hud
        elif k == "budgets" and isinstance(v, dict) and isinstance(out.get("budgets"), dict):
            b = dict(out["budgets"])
            b.update(v)
            out["budgets"] = b
        else:
            out[k] = v
    if "style" not in out:
        raise ValueError("spec needs a style or a template that provides one")
    return out


def playfield_world(tmpl: dict[str, Any]) -> tuple[int, int, int, int]:
    cw, ch = tmpl["compose"]
    ow, oh = tmpl["output"]
    sx, sy = ow / cw, oh / ch
    hud = tmpl["hud"]
    left = int(round(hud["left"] / sx))
    top = int(round(hud["top"] / sy))
    right = cw - int(round(hud["right"] / sx))
    bottom = ch - int(round(hud["bottom"] / sy))
    return left, top, right, bottom


def _coalesce_cells(cells: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    by_row: dict[int, list[int]] = {}
    for xx, yy in cells:
        by_row.setdefault(yy, []).append(xx)
    runs: list[tuple[int, int, int, int]] = []
    for yy, xs in sorted(by_row.items()):
        xs = sorted(set(xs))
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
    for i, (c0, r0, w0, h0) in enumerate(runs):
        if used[i]:
            continue
        h_acc = h0
        for j in range(i + 1, len(runs)):
            c1, r1, w1, h1 = runs[j]
            if c1 == c0 and w1 == w0 and r1 == r0 + h_acc:
                used[j] = True
                h_acc += h1
            elif r1 > r0 + h_acc:
                break
        merged.append((c0, r0, w0, h_acc))
    return merged


def compile_spec(spec: dict[str, Any]) -> dict[str, Any]:
    tmpl = merge_template(spec)
    style = tmpl["style"]
    cw, ch = tmpl["compose"]
    grid = int(tmpl["grid"])
    tile_size = int(tmpl.get("tile_size") or grid)
    nearest = bool(tmpl.get("nearest"))
    issues: list[Issue] = []
    layers: list[dict[str, Any]] = []
    placements: list[dict[str, Any]] = []

    def add_issue(sev, code, message, subject="", fix=""):
        issues.append(Issue(sev, code, message, subject, fix))

    background = tmpl.get("background") or {"type": "color", "color": "#141218"}
    if isinstance(background, str):
        if background.startswith("#") or background in {"transparent", "none"}:
            background = {"type": "color", "color": background}
        else:
            background = {"type": "asset", "slug": full_slug(style, background), "mode": "fill"}

    for region in tmpl.get("terrain") or []:
        slug = full_slug(style, region["tile"])
        if slug in SKIP_SLUGS:
            add_issue("error", "skipped_asset", f"Terrain uses a flagged tile {slug}", slug,
                      "Pick a clean variant (often *_variant_a).")
            continue
        m = metrics(slug)
        if m.style != style:
            add_issue("error", "style_lock", f"{slug} is style {m.style}, scene is {style}", slug,
                      "Search again with this style locked.")
        if m.category != "tiles" and region.get("band") not in {"sky", "terrain"}:
            add_issue("warn", "category", f"Terrain entry is category {m.category}, not tiles", slug)
        z_band = default_band(m, region.get("band"))
        cells: list[tuple[int, int]] = []
        if "rect" in region:
            c, r, w, h = [int(v) for v in region["rect"]]
            if w <= 0 or h <= 0:
                add_issue("error", "terrain_rect", f"Terrain rect has non-positive size {region['rect']}", slug)
                continue
            for yy in range(r, r + h):
                for xx in range(c, c + w):
                    cells.append((xx, yy))
        for cell in region.get("cells") or []:
            cells.append((int(cell[0]), int(cell[1])))
        if not cells:
            add_issue("warn", "empty_terrain", "Terrain region has no cells", slug)
            continue
        for c0, r0, w0, h0 in _coalesce_cells(cells):
            lid = region.get("id") or f"t_{m.slug.rsplit('/', 1)[-1]}_{c0}_{r0}"
            layers.append({
                "id": lid,
                "slug": slug,
                "x": c0 * grid,
                "y": r0 * grid,
                "z": BANDS[z_band],
                "scale": 1.0,
                "flip_x": False,
                "visible": True,
                "tile": {"w": w0 * grid, "h": h0 * grid},
                "tile_cell": tile_size,
                "nearest": nearest,
            })

    slots: dict[str, tuple[float, float]] = {}
    for name, at in (tmpl.get("slots") or {}).items():
        slots[name] = (float(at[0]) * grid, float(at[1]) * grid)

    pf = playfield_world(tmpl)

    def resolve_at(item: dict[str, Any]) -> tuple[float, float]:
        if "slot" in item and item["slot"] in slots:
            return slots[item["slot"]]
        if "at_px" in item:
            return float(item["at_px"][0]), float(item["at_px"][1])
        if "at" in item:
            return float(item["at"][0]) * grid, float(item["at"][1]) * grid
        raise ValueError(f"place {item.get('id')!r} needs at, at_px, or slot")

    for item in tmpl.get("place") or []:
        slug = full_slug(style, item["slug"])
        ident = item.get("id") or slug.rsplit("/", 1)[-1]
        if slug in SKIP_SLUGS:
            add_issue("error", "skipped_asset", f"{ident} uses flagged asset {slug}", ident, "Pick a different slug.")
            continue
        m = metrics(slug)
        if m.style != style:
            add_issue("error", "style_lock", f"{ident} is style {m.style}, scene is {style}", ident)
        scale = target_scale(m, tmpl, item.get("scale"))
        flip_x = bool(item.get("flip_x"))
        band = default_band(m, item.get("band"), flying=bool(item.get("flying")))
        feet_x, feet_y = resolve_at(item)
        placements.append({
            "id": ident,
            "slug": slug,
            "metrics": m,
            "scale": scale,
            "flip_x": flip_x,
            "band": band,
            "feet": [feet_x, feet_y],
            "role": item.get("role") or m.category,
        })

    budgets = dict(tmpl.get("budgets") or {})
    counts: dict[str, int] = {}
    for p in placements:
        counts[p["metrics"].category] = counts.get(p["metrics"].category, 0) + 1
    for cat, n in counts.items():
        cap = budgets.get(cat)
        if cap is not None and n > cap:
            add_issue("warn", "density", f"{n} {cat} placed, budget is {cap}", cat,
                      f"Remove {n - cap} {cat}, or raise the template budget.")

    world_idx = [i for i, p in enumerate(placements) if p["band"] == "world"]
    occupied: list[tuple[str, tuple[float, float, float, float]]] = []
    for i in world_idx:
        p = placements[i]
        m = p["metrics"]
        fx, fy = p["feet"]
        fp = footprint(m, fx, fy, p["scale"])
        hits = [oid for oid, ofp in occupied if rects_overlap(fp, ofp)]
        if not hits:
            occupied.append((p["id"], fp))
            continue
        found = None
        # Move away from the first overlapping partner when possible.
        hit_fp = next((ofp for oid, ofp in occupied if oid in hits), None)
        direction = 1
        if hit_fp is not None:
            other_cx = (hit_fp[0] + hit_fp[2]) / 2
            direction = 1 if fx >= other_cx else -1
        d = direction
        for dx, dy in (
            (d * grid, 0), (d * grid * 1.5, 0), (d * grid * 2, 0), (d * grid * 2.5, 0),
            (0, grid), (0, -grid), (d * grid, grid), (d * grid, -grid),
            (-d * grid, 0), (-d * grid * 2, 0),
        ):
            nfx, nfy = fx + dx, fy + dy
            nfp = footprint(m, nfx, nfy, p["scale"])
            if any(rects_overlap(nfp, ofp) for _, ofp in occupied):
                continue
            if nfx < pf[0] or nfx > pf[2] or nfy < pf[1] or nfy > pf[3]:
                continue
            found = (nfx, nfy, nfp)
            break
        if found:
            p["feet"] = [found[0], found[1]]
            p["nudged"] = True
            add_issue("warn", "overlap_nudged",
                      f"{p['id']} overlapped {', '.join(hits)} and was nudged", p["id"],
                      "Place with more space, or leave nudging to the compiler.")
            occupied.append((p["id"], found[2]))
        else:
            add_issue("error", "overlap",
                      f"{p['id']} footprint overlaps {', '.join(hits)} and could not be nudged", p["id"],
                      "Move one of the actors, or drop the lower-priority one.")
            occupied.append((p["id"], fp))

    for p in placements:
        m = p["metrics"]
        fx, fy = p["feet"]
        x, y = topleft_from_feet(m, fx, fy, p["scale"], p["flip_x"])
        sw, sh = int(round(m.width * p["scale"])), int(round(m.height * p["scale"]))
        if p["band"] == "world":
            z = BANDS["world"] + int(round(fy))
        elif p["band"] == "aerial":
            z = BANDS["aerial"] + int(round(fy))
        else:
            z = BANDS[p["band"]]
        layers.append({
            "id": p["id"],
            "slug": p["slug"],
            "x": x,
            "y": y,
            "z": z,
            "scale": p["scale"],
            "flip_x": p["flip_x"],
            "visible": True,
            "band": p["band"],
            "feet": [round(fx, 1), round(fy, 1)],
        })
        if p["band"] in {"world", "aerial"}:
            if fx < pf[0] or fx > pf[2] or fy < pf[1] or fy > pf[3]:
                if fy < pf[1] and p["metrics"].category in {"foliage", "buildings"}:
                    add_issue("info", "hud_zone",
                              f"{p['id']} feet sit in the top margin (often ok for a back row)", p["id"])
                else:
                    add_issue("warn", "hud_zone",
                              f"{p['id']} feet at ({fx:.0f},{fy:.0f}) sit in a reserved HUD dock "
                              f"(playfield x {pf[0]}-{pf[2]}, y {pf[1]}-{pf[3]})",
                              p["id"],
                              "Move it into the playfield so the HUD does not cover the subject.")
        if x + sw < 0 or y + sh < 0 or x > cw or y > ch:
            add_issue("warn", "off_canvas", f"{p['id']} is fully outside the canvas", p["id"])

    if len(layers) > 200:
        add_issue("error", "layer_cap", f"{len(layers)} layers; compose() cap is 200",
                  fix="Coalesce terrain, or cut props.")

    used = set()
    for ly in layers:
        base = str(ly["id"])
        name = base
        n = 2
        while name in used:
            name = f"{base}_{n}"
            n += 1
        ly["id"] = name
        used.add(name)

    hud_spec = dict(tmpl.get("hud") or {})
    for key in (
        "title", "bars", "currency", "meta_lines", "quest_title", "quest_lines",
        "dialogue_speaker", "dialogue_text", "prompts", "hotbar", "hotbar_selected",
        "panel_widget", "dialogue_widget", "frame_widget", "minimap", "radar",
        "title_color", "text_color", "muted_color", "stroke", "currency_icon",
    ):
        if key in tmpl:
            hud_spec[key] = tmpl[key]

    return {
        "id": tmpl.get("id") or spec.get("id") or "scene",
        "width": cw,
        "height": ch,
        "background": background,
        "layers": layers,
        "layer_count": len(layers),
        "meta": {
            "title": tmpl.get("title") or tmpl.get("id"),
            "genre": tmpl.get("genre") or "",
            "style": style,
            "template": spec.get("template"),
            "perspective": tmpl.get("perspective"),
            "compose_size": [cw, ch],
            "output_size": list(tmpl["output"]),
            "upscale": tmpl.get("upscale") or 1,
            "grid": grid,
            "tile_size": tile_size,
            "playfield_world": list(pf),
            "scale_mode": tmpl.get("scale_mode"),
            "notes": "Compiled by compose-v2 (bands, grid terrain, feet y-sort, auto-scale, HUD docks).",
        },
        "hud": hud_spec,
        "template": tmpl,
        "placements": [
            {
                "id": p["id"],
                "slug": p["slug"],
                "band": p["band"],
                "feet": p["feet"],
                "scale": round(float(p["scale"]), 4),
                "category": p["metrics"].category,
                "nudged": bool(p.get("nudged")),
            }
            for p in placements
        ],
        "issues": [i.as_dict() for i in issues],
        "ok": not any(i.severity == "error" for i in issues),
    }


def lint_legacy(doc: dict[str, Any]) -> dict[str, Any]:
    """Diagnose a v1 (flat x/y/z) scene document."""
    issues: list[Issue] = []
    width, height = int(doc["width"]), int(doc["height"])
    meta = doc.get("meta") or {}
    style = meta.get("style") or ""
    up_meta = meta.get("upscale") or {}
    if isinstance(up_meta, dict):
        upscale = int(up_meta.get("factor") or (3 if width <= 800 else 1))
    else:
        upscale = int(up_meta or (3 if width <= 800 else 1))
    out_w, out_h = (meta.get("output_size") or [width * upscale, height * upscale])
    hud = {"margin": 32, "top": 128, "right": 360, "bottom": 208, "left": 32}
    sx, sy = out_w / width, out_h / height
    pf = (
        int(round(hud["left"] / sx)),
        int(round(hud["top"] / sy)),
        width - int(round(hud["right"] / sx)),
        height - int(round(hud["bottom"] / sy)),
    )
    layers = [ly for ly in doc.get("layers") or [] if ly.get("visible", True)]
    styles = set()
    cats: dict[str, int] = {}
    scales: dict[str, list[float]] = {}
    actors: list[dict[str, Any]] = []
    wall_as_cover = 0
    vfx = 0
    offgrid = 0

    for ly in layers:
        slug = str(ly.get("slug") or "")
        if not slug:
            continue
        try:
            m = metrics(slug)
        except Exception as exc:
            issues.append(Issue("error", "missing", f"Cannot resolve {slug}: {exc}", slug))
            continue
        styles.add(m.style)
        cats[m.category] = cats.get(m.category, 0) + 1
        scale = float(ly.get("scale") or 1.0)
        scales.setdefault(m.category, []).append(scale)
        x, y = int(ly.get("x") or 0), int(ly.get("y") or 0)
        z = int(ly.get("z") or 0)
        if ly.get("tile"):
            tw, th = int(ly["tile"]["w"]), int(ly["tile"]["h"])
            grid_guess = 32 if m.width <= 64 else 64
            step = min(m.width, grid_guess)
            if m.category == "tiles" and step and (x % step or y % step):
                offgrid += 1
            if m.subcategory == "wall" and th < m.height and y > height * 0.25:
                wall_as_cover += 1
                issues.append(Issue(
                    "warn", "category_misuse",
                    f"Wall tile {slug} is stamped as a {tw}x{th} mid-floor patch at ({x},{y})",
                    ly.get("id") or slug,
                    "Use props (crates, barrels) for cover, and wall tiles only as a back wall or lip.",
                ))
            continue
        if m.category == "vfx":
            vfx += 1
        fx, fy = feet_from_topleft(m, x, y, scale, bool(ly.get("flip_x")))
        actors.append({
            "id": ly.get("id") or slug,
            "slug": slug,
            "cat": m.category,
            "scale": scale,
            "z": z,
            "feet": (fx, fy),
            "fp": footprint(m, fx, fy, scale),
        })

    if style and any(s != style for s in styles):
        issues.append(Issue("error", "style_lock", f"Scene mixes styles {sorted(styles)}",
                            fix="Lock one style pack."))
    if vfx > 2:
        issues.append(Issue("warn", "density", f"{vfx} VFX stamps; more than 1-2 turns into visual noise",
                            "vfx", "Keep one effect tied to a single event."))
    if offgrid:
        issues.append(Issue("info", "offgrid", f"{offgrid} tiled regions are not aligned to the tile size."))

    overlap_n = 0
    clustered = []
    for i, a in enumerate(actors):
        if a["cat"] in {"decals", "vfx", "tiles"}:
            continue
        for b in actors[i + 1:]:
            if b["cat"] in {"decals", "vfx", "tiles"}:
                continue
            if rects_overlap(a["fp"], b["fp"]):
                overlap_n += 1
                if a["cat"] in {"characters", "creatures", "enemies"} or b["cat"] in {"characters", "creatures", "enemies"}:
                    clustered.append((a["id"], b["id"]))
    if overlap_n:
        issues.append(Issue(
            "error", "overlap",
            f"{overlap_n} footprint overlaps among props/actors"
            + (f", including {len(clustered)} that involve a character or creature" if clustered else ""),
            fix="Y-sort is not enough when sprites share the same ground point. Space feet at least half a sprite apart.",
        ))

    charlike = [a for a in actors if a["cat"] in {"characters", "creatures", "enemies"}]
    if charlike:
        zs = [a["z"] for a in charlike]
        if min(zs) >= 50 and any(p["z"] < 50 for p in actors if p["cat"] in {"props", "foliage", "buildings"}):
            issues.append(Issue(
                "warn", "z_band",
                "Characters use a high fixed z (always on top) while props use a low z. "
                "A character standing behind a tree or crate will still draw in front of it.",
                fix="Put props, foliage, buildings and characters in one WORLD band and y-sort by feet.",
            ))

    for cat, vals in scales.items():
        if cat in {"tiles", "backgrounds"} or len(vals) < 2:
            continue
        lo, hi = min(vals), max(vals)
        if hi > 0 and (hi - lo) / hi > 0.25 and cat in {"characters", "props", "enemies", "creatures"}:
            issues.append(Issue(
                "warn", "scale_mismatch",
                f"{cat} scales range {lo:.2f}-{hi:.2f} ({(hi-lo)/hi:.0%} spread)",
                cat,
                "Normalize each category to one target height in the style profile.",
            ))

    covered = 0
    for a in actors:
        if a["cat"] in {"decals", "vfx"}:
            continue
        fx, fy = a["feet"]
        if (fx < pf[0] or fx > pf[2] or fy < pf[1] or fy > pf[3]) and (fy > pf[3] or fx > pf[2]):
            covered += 1
    if covered:
        issues.append(Issue(
            "warn", "hud_zone",
            f"{covered} actors have their feet in the reserved bottom/right HUD docks "
            f"(world playfield x {pf[0]}-{pf[2]}, y {pf[1]}-{pf[3]})",
            fix="Anchor HUD to edges, reserve those docks, and keep the subject in the remaining playfield.",
        ))

    dens = {k: cats.get(k, 0) for k in ("characters", "creatures", "enemies", "props", "foliage", "vfx", "buildings")}
    issues.append(Issue("info", "counts", "Category counts: " + ", ".join(f"{k}={v}" for k, v in dens.items() if v)))

    has_bg = any("/backgrounds/scene/" in str(ly.get("slug") or "") for ly in layers)
    has_floor = any("/tiles/floor/" in str(ly.get("slug") or "") for ly in layers)
    if has_bg and has_floor:
        issues.append(Issue(
            "warn", "perspective",
            "A painted/photo background is composited under an orthographic tiled floor. "
            "The two spatial systems fight at the floor/wall join.",
            fix="Pick one ground plane. For a painted hall, do not tile a walkable floor over it.",
        ))

    return {
        "id": doc.get("id"),
        "style": style,
        "size": [width, height],
        "upscale": upscale,
        "playfield_world": list(pf),
        "layer_count": len(layers),
        "category_counts": cats,
        "overlap_pairs": overlap_n,
        "character_overlaps": len(clustered),
        "vfx": vfx,
        "wall_as_cover": wall_as_cover,
        "issues": [i.as_dict() for i in issues],
        "ok": not any(i.severity == "error" for i in issues),
    }
