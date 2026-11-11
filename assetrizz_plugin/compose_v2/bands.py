"""Layer bands and catalog-category defaults for compose-v2.

Band bases increase with draw order. The ``world`` band is y-sorted by the
feet pivot, so callers add the feet y coordinate to ``BANDS["world"]`` instead
of using the bare base (see :func:`assetrizz_plugin.compose_v2.layout.band_z`).
"""

from __future__ import annotations

SKIP_SLUGS = frozenset(
    {
        "pixel_32/tiles/floor/dirt_base",
        "pixel_32/tiles/floor/dirt_path_base",
        "pixel_32/tiles/floor/dirt_variant_b",
        "pixel_32/tiles/floor/farm_soil_base",
        "pixel_32/tiles/floor/farm_soil_variant_b",
        "pixel_32/tiles/floor/grass_variant_b",
        "pixel_32/tiles/floor/flower_meadow_variant_b",
        "pixel_32/tiles/floor/shallow_water_base",
        "pixel_32/tiles/floor/shallow_water_variant_b",
        "pixel_32/tiles/floor/metal_plate_base",
        "pixel_32/tiles/floor/stone_floor_base",
        "pixel_32/tiles/floor/snow_base",
        "pixel_32/tiles/floor/tall_grass_base",
        "pixel_32/tiles/wall/wood_fence_base",
        "pixel_32/tiles/wall/wood_fence_variant_b",
        "pixel_32/tiles/wall/wood_wall_base",
        "pixel_32/tiles/wall/hedge_base",
        "pixel_32/tiles/wall/hedge_variant_a",
        "pixel_32/tiles/wall/hedge_variant_b",
        "pixel_32/tiles/wall/metal_wall_variant_b",
        "pixel_32/foliage/bush/round_hedge_plain",
        "flat_vector_ui/tiles/floor/crystal_floor_base",
        "flat_vector_ui/tiles/floor/crystal_floor_variant_a",
        "flat_vector_ui/tiles/floor/crystal_floor_variant_b",
        "flat_vector_ui/tiles/floor/shallow_water_variant_b",
        "flat_vector_ui/tiles/floor/metal_plate_variant_a",
        "flat_vector_ui/tiles/floor/flower_meadow_variant_b",
        "flat_vector_ui/tiles/floor/ice_base",
        "flat_vector_ui/tiles/wall/stone_wall_base",
        "flat_vector_ui/tiles/wall/windowed_wall_variant_a",
        "flat_vector_ui/tiles/wall/cave_wall_base",
    }
)

BANDS = {
    "sky": 0,
    "terrain": 1000,
    "decal": 2000,
    "world": 3000,
    "aerial": 8000,
    "hud": 10000,
}

CATEGORY_BAND = {
    "backgrounds": "sky",
    "sky": "sky",
    "tiles": "terrain",
    "terrain": "terrain",
    "decals": "decal",
    "characters": "world",
    "creatures": "world",
    "enemies": "world",
    "props": "world",
    "foliage": "world",
    "buildings": "world",
    "furniture": "world",
    "vehicles": "world",
    "weapons": "world",
    "effects": "aerial",
    "vfx": "aerial",
    "particles": "aerial",
    "weather": "aerial",
    "markers": "aerial",
    "ui": "hud",
    "icons": "hud",
    "portraits": "hud",
}
