"""CV04: genre templates and the compose-v2 lint pass.

All asset metrics are injected; these tests never touch the large local
library or the network.
"""

from __future__ import annotations

import pytest

from assetrizz_plugin.compose_v2 import Metrics
from assetrizz_plugin.compose_v2 import compile as compile_mod
from assetrizz_plugin.compose_v2.compile import compile_spec, merge_template, playfield_world
from assetrizz_plugin.compose_v2.lint import Issue, lint_compiled, lint_legacy
from assetrizz_plugin.compose_v2.templates import TEMPLATES

GRASS = "pixel_32/tiles/floor/grass_base"
WALL = "pixel_32/tiles/wall/wood_wall_variant_a"
HERO = "pixel_32/characters/humanoid/hero_front"
CRATE = "pixel_32/props/object/crate_plain"
COZY_CRATE = "cozy_cartoon/props/object/crate_plain"


def _metrics_table() -> dict[str, Metrics]:
    return {
        GRASS: Metrics(
            width=16,
            height=16,
            category="tiles",
            subcategory="floor",
            slug=GRASS,
            style="pixel_32",
        ),
        WALL: Metrics(
            width=32,
            height=64,
            category="tiles",
            subcategory="wall",
            slug=WALL,
            style="pixel_32",
        ),
        HERO: Metrics(
            width=32,
            height=48,
            bbox=(4, 8, 28, 44),
            category="characters",
            subcategory="humanoid",
            slug=HERO,
            style="pixel_32",
        ),
        CRATE: Metrics(
            width=24,
            height=24,
            category="props",
            subcategory="object",
            slug=CRATE,
            style="pixel_32",
        ),
        COZY_CRATE: Metrics(
            width=24,
            height=24,
            category="props",
            subcategory="object",
            slug=COZY_CRATE,
            style="cozy_cartoon",
        ),
    }


def _fake_metrics(slug: str) -> Metrics:
    try:
        return _metrics_table()[slug]
    except KeyError as exc:  # pragma: no cover - defensive test helper
        raise AssertionError(f"unexpected asset {slug}") from exc


@pytest.fixture()
def injected_compile_metrics(monkeypatch):
    table = _metrics_table()

    def fake_metrics(slug: str) -> Metrics:
        try:
            return table[slug]
        except KeyError as exc:  # pragma: no cover - defensive test helper
            raise AssertionError(f"unexpected asset {slug}") from exc

    monkeypatch.setattr(compile_mod, "metrics", fake_metrics)
    return table


def _doc(
    *,
    template_name: str = "topdown_farming",
    style: str | None = None,
    width: int = 128,
    height: int = 96,
    layers: list[dict] | None = None,
    placements: list[dict] | None = None,
    background: dict | None = None,
    spec: dict | None = None,
    template_extra: dict | None = None,
) -> dict:
    template = dict(TEMPLATES[template_name])
    style = style or template["style"]
    template["style"] = style
    if template_extra:
        template.update(template_extra)
    field = playfield_world(template)
    return {
        "width": width,
        "height": height,
        "background": background or {"type": "color", "color": "#101018"},
        "layers": list(layers or []),
        "layer_count": len(layers or []),
        "template": template,
        "meta": {
            "style": style,
            "template": template_name,
            "grid": int(template["grid"]),
            "compose_size": [width, height],
            "output_size": list(template["output"]),
            "playfield_world": list(field),
        },
        "placements": list(placements or []),
        "spec": spec,
        "issues": [],
        "ok": True,
    }


def _codes(issues: list[Issue]) -> set[str]:
    return {issue.code for issue in issues}


def _of(issues: list[Issue], code: str) -> list[Issue]:
    return [issue for issue in issues if issue.code == code]


def test_four_genre_templates_exist_and_merge_into_a_spec():
    expected = {"topdown_farming", "topdown_shooter", "dungeon_crawler", "side_platformer"}
    assert expected <= set(TEMPLATES)

    for name in expected:
        template = TEMPLATES[name]
        assert template["style"]
        assert len(template["compose"]) == 2
        assert len(template["output"]) == 2
        assert int(template["grid"]) > 0
        assert int(template["tile_size"]) > 0
        assert template["scale_mode"] in {"native", "target"}
        assert isinstance(template["budgets"], dict) and template["budgets"]
        for key in ("margin", "top", "right", "bottom", "left"):
            assert key in template["hud"]
        if template["scale_mode"] == "target":
            assert template["target_px"]

        merged = merge_template(
            {
                "template": name,
                "style": template["style"],
                "budgets": {"props": 99},
            }
        )
        assert merged["style"] == template["style"]
        assert merged["compose"] == [int(value) for value in template["compose"]]
        assert merged["grid"] == int(template["grid"])
        assert merged["tile_size"] == int(template["tile_size"])
        assert merged["scale_mode"] == template["scale_mode"]
        assert merged["hud"] == template["hud"]
        assert merged["budgets"]["props"] == 99
        if "characters" in template["budgets"]:
            assert merged["budgets"]["characters"] == template["budgets"]["characters"]


def test_lint_reports_world_footprint_overlap_with_a_fix():
    doc = _doc(
        placements=[
            {
                "id": "hero",
                "slug": HERO,
                "band": "world",
                "feet": [64, 64],
                "scale": 1.0,
                "category": "characters",
            },
            {
                "id": "crate",
                "slug": CRATE,
                "band": "world",
                "feet": [64, 64],
                "scale": 1.0,
                "category": "props",
            },
        ]
    )

    issues = lint_compiled(doc, metrics_fn=_fake_metrics)
    overlap = _of(issues, "overlap")

    assert overlap
    assert overlap[0].severity == "error"
    assert "hero" in overlap[0].message and "crate" in overlap[0].message
    assert "space" in overlap[0].fix.lower()


def test_lint_compiled_defaults_to_the_compiler_metric_resolver(injected_compile_metrics):
    doc = _doc(
        placements=[
            {
                "id": "hero",
                "slug": HERO,
                "band": "world",
                "feet": [64, 64],
                "scale": 1.0,
                "category": "characters",
            },
            {
                "id": "crate",
                "slug": CRATE,
                "band": "world",
                "feet": [64, 64],
                "scale": 1.0,
                "category": "props",
            },
        ]
    )

    issues = lint_compiled(doc)

    assert _of(issues, "overlap")


def test_lint_reports_density_budget_overrun_with_budget_hint():
    placements = []
    positions = [(20, 30), (40, 30), (60, 30), (80, 30), (100, 30),
                 (20, 60), (40, 60), (60, 60), (80, 60), (100, 60),
                 (40, 75)]
    for index, (x, y) in enumerate(positions):
        placements.append(
            {
                "id": f"crate_{index}",
                "slug": CRATE,
                "band": "world",
                "feet": [x, y],
                "scale": 1.0,
                "category": "props",
            }
        )

    issues = lint_compiled(_doc(placements=placements), metrics_fn=_fake_metrics)
    density = _of(issues, "density")

    assert density
    assert density[0].severity == "warn"
    assert density[0].subject == "props"
    assert "11" in density[0].message and "10" in density[0].message
    assert "props" in density[0].fix.lower() and "budget" in density[0].fix.lower()


def test_lint_reports_actor_in_a_hud_dock_outside_the_playfield():
    doc = _doc(
        placements=[
            {
                "id": "hero",
                "slug": HERO,
                "band": "world",
                "feet": [20, 5],
                "scale": 1.0,
                "category": "characters",
            },
        ]
    )

    issues = lint_compiled(doc, metrics_fn=_fake_metrics)
    hud = _of(issues, "hud_zone")

    assert hud
    assert hud[0].subject == "hero"
    assert "playfield" in hud[0].message.lower()
    assert "playfield" in hud[0].fix.lower()


def test_lint_reports_off_canvas_placement():
    doc = _doc(
        layers=[
            {
                "id": "lost",
                "slug": CRATE,
                "x": -500,
                "y": -500,
                "z": 3000,
                "scale": 1.0,
                "visible": True,
            },
        ]
    )

    issues = lint_compiled(doc, metrics_fn=_fake_metrics)
    off = _of(issues, "off_canvas")

    assert off
    assert off[0].subject == "lost"
    assert "canvas" in off[0].fix.lower()


def test_lint_reports_wall_tile_used_as_floor():
    doc = _doc(
        layers=[
            {
                "id": "bad_ground",
                "slug": WALL,
                "x": 32,
                "y": 64,
                "z": 1000,
                "scale": 1.0,
                "visible": True,
                "tile": {"w": 32, "h": 32},
                "tile_cell": 16,
            },
        ]
    )

    issues = lint_compiled(doc, metrics_fn=_fake_metrics)
    wall = _of(issues, "wall_as_floor")

    assert wall
    assert wall[0].severity in {"warn", "error"}
    assert "wall" in wall[0].message.lower()
    assert "floor" in wall[0].fix.lower()


def test_lint_reports_style_mixing_with_a_style_lock_hint():
    doc = _doc(
        layers=[
            {
                "id": "mixed",
                "slug": COZY_CRATE,
                "x": 0,
                "y": 0,
                "z": 3000,
                "scale": 1.0,
                "visible": True,
            },
        ]
    )

    issues = lint_compiled(doc, metrics_fn=_fake_metrics)
    style = _of(issues, "style_lock")

    assert style
    assert style[0].severity == "error"
    assert style[0].subject == "mixed"
    assert "style" in style[0].fix.lower()


def test_lint_enforces_the_template_layer_cap():
    layers = [
        {
            "id": f"layer_{index}",
            "slug": CRATE,
            "x": 0,
            "y": 0,
            "z": 3000,
            "scale": 1.0,
            "visible": True,
        }
        for index in range(201)
    ]

    issues = lint_compiled(_doc(layers=layers), metrics_fn=_fake_metrics)
    cap = _of(issues, "layer_cap")

    assert cap
    assert cap[0].severity == "error"
    assert "layer" in cap[0].fix.lower()


def test_lint_reports_unknown_template_and_grid_misalignment():
    unknown = _doc()
    unknown["meta"]["template"] = "mystery"
    issues = lint_compiled(unknown, metrics_fn=_fake_metrics)
    bad_template = _of(issues, "unknown_template")
    assert bad_template
    assert bad_template[0].severity == "error"
    assert "topdown_farming" in bad_template[0].fix

    offgrid = _doc(
        layers=[
            {
                "id": "offgrid",
                "slug": GRASS,
                "x": 5,
                "y": 7,
                "z": 1000,
                "scale": 1.0,
                "visible": True,
                "tile": {"w": 16, "h": 16},
            },
        ]
    )
    issues = lint_compiled(offgrid, metrics_fn=_fake_metrics)
    grid = _of(issues, "grid_misalign")
    assert grid
    assert grid[0].fix
    assert "32" in grid[0].message or "32" in grid[0].fix


def test_compile_spec_merges_lint_issues_through_the_hook(injected_compile_metrics):
    spec = {
        "id": "wall-yard",
        "template": "topdown_farming",
        "style": "pixel_32",
        "compose": [128, 96],
        "grid": 16,
        "terrain": [
            {"id": "ground", "tile": "tiles/floor/grass_base", "rect": [0, 0, 4, 3]},
            {"id": "bad_wall", "tile": "tiles/wall/wood_wall_variant_a", "rect": [0, 4, 2, 1]},
        ],
        "place": [],
    }

    compiled = compile_spec(spec)

    assert all(isinstance(issue, Issue) for issue in compiled["issues"])
    wall = _of(compiled["issues"], "wall_as_floor")
    assert wall
    assert wall[0].fix
    assert compiled["ok"] is True


def test_lint_legacy_runs_on_a_v1_scene_document():
    doc = {
        "id": "legacy-yard",
        "width": 320,
        "height": 180,
        "meta": {"style": "pixel_32", "upscale": {"factor": 3}},
        "layers": [
            {
                "id": "ground",
                "slug": GRASS,
                "x": 0,
                "y": 0,
                "z": 0,
                "scale": 1.0,
                "tile": {"w": 160, "h": 96},
            },
            {"id": "hero", "slug": HERO, "x": 100, "y": 100, "z": 10, "scale": 1.0},
            {"id": "crate", "slug": CRATE, "x": 100, "y": 124, "z": 5, "scale": 1.0},
            {"id": "mixed", "slug": COZY_CRATE, "x": 200, "y": 100, "z": 5, "scale": 1.0},
            {
                "id": "wall",
                "slug": WALL,
                "x": 32,
                "y": 100,
                "z": 0,
                "scale": 1.0,
                "tile": {"w": 32, "h": 32},
            },
            {"id": "off", "slug": CRATE, "x": -500, "y": -500, "z": 5, "scale": 1.0},
        ],
    }

    issues = lint_legacy(doc, metrics_fn=_fake_metrics)
    codes = _codes(issues)

    assert isinstance(issues, list)
    assert all(isinstance(issue, Issue) for issue in issues)
    assert {"overlap", "style_lock", "wall_as_floor", "off_canvas", "hud_zone"} <= codes
    for code in ("overlap", "style_lock", "wall_as_floor", "off_canvas", "hud_zone"):
        assert all(issue.fix for issue in _of(issues, code))
