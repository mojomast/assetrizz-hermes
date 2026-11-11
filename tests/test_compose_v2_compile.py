"""CV02: declarative spec compilation and the assetrizz_scene compose op.

All asset metrics are injected; nothing here needs the large local library or
the network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from assetrizz_plugin.compose_v2 import BANDS, Metrics
from assetrizz_plugin.compose_v2 import compile as compile_mod
from assetrizz_plugin.compose_v2.compile import Issue, compile_spec
from assetrizz_plugin.tools import SCENE_OPS, SCHEMA_SCENE, handle_scene_safe, measure_schemas


def _metrics() -> dict[str, Metrics]:
    return {
        "pixel_32/tiles/floor/grass_base": Metrics(
            width=16,
            height=16,
            category="tiles",
            subcategory="floor",
            slug="pixel_32/tiles/floor/grass_base",
            style="pixel_32",
        ),
        "pixel_32/tiles/floor/dirt_path_variant_a": Metrics(
            width=16,
            height=16,
            category="tiles",
            subcategory="floor",
            slug="pixel_32/tiles/floor/dirt_path_variant_a",
            style="pixel_32",
        ),
        "pixel_32/characters/humanoid/hero_front": Metrics(
            width=32,
            height=48,
            bbox=(4, 8, 28, 44),
            category="characters",
            subcategory="humanoid",
            slug="pixel_32/characters/humanoid/hero_front",
            style="pixel_32",
        ),
        "pixel_32/props/object/crate_plain": Metrics(
            width=24,
            height=24,
            category="props",
            subcategory="object",
            slug="pixel_32/props/object/crate_plain",
            style="pixel_32",
        ),
    }


@pytest.fixture()
def injected_metrics(monkeypatch):
    table = _metrics()

    def fake_metrics(slug: str) -> Metrics:
        try:
            return table[slug]
        except KeyError as exc:  # pragma: no cover - defensive test helper
            raise AssertionError(f"unexpected asset {slug}") from exc

    monkeypatch.setattr(compile_mod, "metrics", fake_metrics)
    return table


def _spec() -> dict:
    return {
        "id": "test-yard",
        "template": "topdown_farming",
        "style": "pixel_32",
        "compose": [128, 96],
        "grid": 16,
        "background": "#112233",
        "slots": {"crate_spot": [3, 4]},
        "terrain": [
            {
                "id": "floor",
                "tile": "tiles/floor/grass_base",
                "cells": [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1]],
            },
            {
                "id": "path",
                "tile": "tiles/floor/dirt_path_variant_a",
                "rect": [4, 2, 2, 3],
            },
        ],
        "place": [
            {"id": "hero", "slug": "characters/humanoid/hero_front", "at": [4, 5]},
            {
                "id": "crate",
                "slug": "props/object/crate_plain",
                "slot": "crate_spot",
                "flip_x": True,
                "band": "decal",
                "scale": 1.5,
            },
        ],
    }


def test_compile_spec_coalesces_terrain_and_emits_ordinary_layers(injected_metrics):
    compiled = compile_spec(_spec())

    assert compiled["ok"] is True
    assert compiled["id"] == "test-yard"
    assert compiled["width"] == 128
    assert compiled["height"] == 96
    assert compiled["background"] == {"type": "color", "color": "#112233"}
    assert compiled["layer_count"] == len(compiled["layers"]) == 4

    layers = {layer["id"]: layer for layer in compiled["layers"]}

    floor = layers["floor"]
    assert floor["slug"] == "pixel_32/tiles/floor/grass_base"
    assert (floor["x"], floor["y"]) == (0, 0)
    assert floor["tile"] == {"w": 48, "h": 32}
    assert floor["z"] == BANDS["terrain"]

    path = layers["path"]
    assert path["slug"] == "pixel_32/tiles/floor/dirt_path_variant_a"
    assert (path["x"], path["y"]) == (64, 32)
    assert path["tile"] == {"w": 32, "h": 48}

    hero = layers["hero"]
    assert (hero["x"], hero["y"]) == (48, 32)
    assert hero["scale"] == 1.0
    assert hero["z"] == BANDS["world"] + 80
    assert hero["feet"] == [64.0, 80.0]

    crate = layers["crate"]
    assert crate["band"] == "decal"
    assert crate["z"] == BANDS["decal"]
    assert crate["flip_x"] is True
    assert crate["scale"] == 1.5
    assert (crate["x"], crate["y"]) == (30, 28)
    assert crate["feet"] == [48.0, 64.0]

    for layer in compiled["layers"]:
        assert "slug" in layer
        assert "x" in layer and "y" in layer
        assert "z" in layer and "scale" in layer


def test_compile_spec_returns_issue_objects_with_fixes(injected_metrics):
    spec = {
        "id": "broken",
        "template": "topdown_farming",
        "style": "pixel_32",
        "compose": [64, 48],
        "grid": 16,
        "terrain": [
            {"id": "bad_floor", "tile": "tiles/floor/dirt_base", "rect": [0, 0, 1, 1]},
        ],
        "place": [
            {"id": "lost", "slug": "props/object/crate_plain"},
        ],
    }

    compiled = compile_spec(spec)

    assert compiled["ok"] is False
    assert compiled["issues"]
    assert all(isinstance(issue, Issue) for issue in compiled["issues"])
    by_code = {issue.code: issue for issue in compiled["issues"]}
    assert by_code["skipped_asset"].severity == "error"
    assert by_code["skipped_asset"].fix
    assert by_code["missing_position"].severity == "error"
    assert by_code["skipped_asset"].as_dict()["code"] == "skipped_asset"
    assert by_code["skipped_asset"]["code"] == "skipped_asset"


def test_compose_op_accepts_a_spec_string_and_renders(plugin_env):
    spec = {
        "id": "level-compose",
        "template": "topdown_farming",
        "style": "pixel_32",
        "compose": [64, 48],
        "grid": 16,
        "background": "#223344",
        "terrain": [
            {"id": "floor", "tile": "tiles/floor/grass_base", "rect": [0, 0, 4, 3]},
        ],
        "place": [
            {"id": "hero", "slug": "characters/humanoid/ranger_front", "at": [2, 2]},
        ],
        "hud": {"title": "TEST YARD"},
    }

    result = json.loads(
        handle_scene_safe(
            {
                "op": "compose",
                "name": "level-compose",
                "spec": json.dumps(spec),
            }
        )
    )

    assert result["ok"] is True
    assert result["scene"]["id"] == "level-compose"
    assert result["scene"]["layer_count"] == 2
    assert [layer["slug"] for layer in result["scene"]["layers"]] == [
        "pixel_32/tiles/floor/grass_base",
        "pixel_32/characters/humanoid/ranger_front",
    ]
    assert isinstance(result["issues"], list)
    png = Path(result["png"])
    assert png.is_file()
    with Image.open(png) as image:
        assert image.size == (64, 48)


def test_compose_op_rejects_a_non_object_spec(plugin_env):
    result = json.loads(handle_scene_safe({"op": "compose", "spec": "[1, 2]"}))
    assert result["ok"] is False
    assert result["code"] == "invalid_args"

    result = json.loads(handle_scene_safe({"op": "compose", "spec": "not json"}))
    assert result["ok"] is False
    assert result["code"] == "invalid_args"


def test_existing_place_and_tile_ops_still_work(plugin_env):
    assert json.loads(handle_scene_safe({"op": "create", "name": "legacy", "width": 48, "height": 32}))[
        "ok"
    ]
    tiled = json.loads(
        handle_scene_safe(
            {
                "op": "tile",
                "slug": "pixel_32/tiles/floor/grass_base",
                "x": 0,
                "y": 0,
                "tile_w": 48,
                "tile_h": 32,
            }
        )
    )
    placed = json.loads(
        handle_scene_safe(
            {"op": "place", "slug": "pixel_32/props/object/crate_plain", "x": 8, "y": 12, "z": 2}
        )
    )
    assert tiled["ok"] is True
    assert placed["ok"] is True
    assert placed["layer"]["x"] == 8
    assert placed["layer"]["y"] == 12


def test_scene_schema_adds_only_compose_and_an_opaque_spec_string():
    assert "compose" in SCENE_OPS
    for op in (
        "create",
        "place",
        "move",
        "scale",
        "flip",
        "layer",
        "remove",
        "tile",
        "list",
        "clear",
        "render",
        "save",
        "load",
    ):
        assert op in SCENE_OPS

    parameters = SCHEMA_SCENE["parameters"]
    assert parameters["additionalProperties"] is False
    assert list(parameters["properties"]["op"]["enum"]) == list(SCENE_OPS)
    spec = parameters["properties"]["spec"]
    assert spec["type"] == "string"
    assert "properties" not in spec

    counts = measure_schemas()
    assert counts["o200k_base"] <= 931 + 80
    assert counts["cl100k_base"] <= 918 + 80
