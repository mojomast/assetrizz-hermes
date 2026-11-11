"""CV01: bands, injected metrics, feet/top-left layout, and auto-scale."""

from __future__ import annotations

import pytest

from assetrizz_plugin.compose_v2 import (
    BANDS,
    CATEGORY_BAND,
    DEFAULT_PIVOT,
    Metrics,
    band_z,
    default_band,
    feet_from_topleft,
    metrics_from_asset,
    normalize_pivot,
    target_scale,
    topleft_from_feet,
)


def _hero(**overrides) -> Metrics:
    kwargs = dict(
        width=32,
        height=48,
        bbox=(4, 8, 28, 44),
        category="characters",
        subcategory="humanoid",
        slug="pixel_32/characters/humanoid/hero_front",
        style="pixel_32",
        pivot=DEFAULT_PIVOT,
    )
    kwargs.update(overrides)
    return Metrics(**kwargs)


def test_bands_have_increasing_z_bases():
    assert list(BANDS) == ["sky", "terrain", "decal", "world", "aerial", "hud"]
    bases = [BANDS[name] for name in BANDS]
    assert bases == sorted(bases)
    assert len(set(bases)) == len(bases)
    assert BANDS["sky"] < BANDS["terrain"] < BANDS["decal"] < BANDS["world"]
    assert BANDS["world"] < BANDS["aerial"] < BANDS["hud"]


def test_category_band_maps_catalog_categories():
    assert CATEGORY_BAND["characters"] == "world"
    assert CATEGORY_BAND["tiles"] == "terrain"
    assert CATEGORY_BAND["buildings"] == "world"
    assert CATEGORY_BAND["props"] == "world"
    assert CATEGORY_BAND["effects"] == "aerial"
    assert CATEGORY_BAND["vfx"] == "aerial"
    assert CATEGORY_BAND["ui"] == "hud"
    assert CATEGORY_BAND["backgrounds"] == "sky"
    assert CATEGORY_BAND["decals"] == "decal"


def test_world_band_z_sorts_by_feet_y():
    low = band_z("world", 120)
    high = band_z("world", 480)
    assert low == BANDS["world"] + 120
    assert high == BANDS["world"] + 480
    assert low < high


def test_non_sorted_band_ignores_feet_y():
    assert band_z("terrain", 999) == BANDS["terrain"]
    assert band_z("hud", 999) == BANDS["hud"]


def test_default_band_uses_category_explicit_and_flying_overrides():
    hero = _hero()
    tile = _hero(category="tiles", subcategory="floor")
    effect = _hero(category="effects", subcategory="spark")
    flyer = _hero(category="vehicles", subcategory="air")
    assert default_band(hero) == "world"
    assert default_band(tile) == "terrain"
    assert default_band(effect) == "aerial"
    assert default_band(flyer) == "aerial"
    assert default_band(hero, flying=True) == "aerial"
    assert default_band(hero, "decal") == "decal"
    assert default_band(tile, "world", flying=True) == "world"
    assert default_band(_hero(category="unknown"), "aerial") == "aerial"


def test_default_band_unknown_category_falls_back_to_world():
    assert default_band(_hero(category="mystery")) == "world"


def test_feet_and_topleft_round_trip_with_default_bottom_center_pivot():
    hero = _hero()
    assert hero.pivot == (0.5, 1.0)

    feet = feet_from_topleft(hero, 100, 50, 2.0)
    assert feet == (132.0, 146.0)
    assert topleft_from_feet(hero, *feet, 2.0) == (100, 50)


def test_feet_conversion_respects_custom_pivot_and_flip():
    hero = _hero(pivot=(0.2, 0.8))
    assert feet_from_topleft(hero, 10, 20, 2.0) == (10 + 2 * 32 * 0.2, 20 + 2 * 48 * 0.8)

    flipped = feet_from_topleft(hero, 10, 20, 2.0, True)
    assert flipped == (10 + 2 * 32 * 0.8, 20 + 2 * 48 * 0.8)
    assert topleft_from_feet(hero, *flipped, 2.0, True) == (10, 20)


def test_normalize_pivot_accepts_json_dict_sequence_and_defaults():
    assert normalize_pivot(None) == DEFAULT_PIVOT
    assert normalize_pivot('{"x": 0.25, "y": 0.75}') == (0.25, 0.75)
    assert normalize_pivot({"x": 0.3}) == (0.3, 1.0)
    assert normalize_pivot([0.4, 0.6]) == (0.4, 0.6)
    assert normalize_pivot("not-json") == DEFAULT_PIVOT


def test_metrics_from_asset_uses_injected_dimensions_bbox_and_pivot():
    asset = {
        "slug": "pixel_32/characters/humanoid/ranger_front",
        "width": 64,
        "height": 96,
        "category": "characters",
        "subcategory": "humanoid",
        "style_pack": "pixel_32",
        "pivot": '{"x": 0.4, "y": 0.9}',
        "tileable": False,
        "path": "assets/pixel_32/characters/humanoid/ranger_front.png",
    }
    m = metrics_from_asset(asset, width=64, height=96, bbox=(8, 16, 56, 88))

    assert m.width == 64
    assert m.height == 96
    assert m.bbox == (8, 16, 56, 88)
    assert m.vis_w == 48
    assert m.vis_h == 72
    assert m.category == "characters"
    assert m.subcategory == "humanoid"
    assert m.style == "pixel_32"
    assert m.pivot == (0.4, 0.9)
    assert m.tileable is False


def test_metrics_from_asset_defaults_missing_pivot_to_bottom_center():
    m = metrics_from_asset(
        {
            "slug": "pixel_32/props/object/crate_plain",
            "width": 24,
            "height": 24,
            "category": "props",
        }
    )
    assert m.bbox == (0, 0, 24, 24)
    assert m.pivot == DEFAULT_PIVOT
    assert m.style == ""


def test_target_scale_native_modes_return_one_and_override_wins():
    hero = _hero()
    for mode in ("native", "style", "style_native"):
        assert target_scale(hero, {"scale_mode": mode}) == 1.0
    assert target_scale(hero, {"scale_mode": "target", "target_px": {"characters": 200}}) == 200 / 36
    assert target_scale(hero, {"scale_mode": "target", "target_px": {"characters": 200}}, 0.75) == 0.75


def test_target_scale_prefers_subcategory_then_category():
    hero = _hero()
    template = {
        "scale_mode": "target",
        "target_px": {
            "characters": 180,
            "characters/humanoid": 90,
            "props": 60,
        },
    }
    assert target_scale(hero, template) == pytest.approx(90 / 36)
    assert target_scale(_hero(subcategory="beast"), template) == pytest.approx(180 / 36)
    assert target_scale(_hero(category="props", subcategory="object"), template) == pytest.approx(60 / 36)


def test_target_scale_supports_subject_targets_and_missing_falls_back():
    hero = _hero()
    template = {
        "scale_mode": "target",
        "target_px_subject": {"characters/humanoid": 72},
    }
    assert target_scale(hero, template) == pytest.approx(72 / 36)
    assert target_scale(hero, {"scale_mode": "target"}) == 1.0


def test_target_scale_clamps_to_safe_range():
    tall = _hero(bbox=(0, 0, 32, 2000))
    tiny = _hero(bbox=(0, 0, 32, 1))
    assert target_scale(tall, {"scale_mode": "target", "target_px": {"characters": 1}}) == 0.05
    assert target_scale(tiny, {"scale_mode": "target", "target_px": {"characters": 100000}}) == 8.0


def test_target_scale_uses_visible_bbox_height_not_full_canvas():
    hero = _hero(width=100, height=200, bbox=(0, 50, 100, 150))
    assert target_scale(hero, {"scale_mode": "target", "target_px": {"characters": 150}}) == pytest.approx(1.5)


def test_metrics_are_injectable_without_library_access():
    m = _hero()
    feet_x, feet_y = feet_from_topleft(m, 0, 0, 1.0)
    assert (feet_x, feet_y) == (16.0, 48.0)
    assert band_z("world", feet_y) == BANDS["world"] + 48
