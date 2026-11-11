"""Genre templates for compose-v2.

Each template fixes the composition size, grid, scale policy, density budgets,
and HUD dock reservations for one genre. Specs merge over a template by name
(see :func:`assetrizz_plugin.compose_v2.compile.merge_template`).
"""

from __future__ import annotations

from typing import Any

from .hud import HUD_DOCKS

TEMPLATES: dict[str, dict[str, Any]] = {
    "topdown_farming": {
        "genre": "cozy top-down farming / life sim",
        "perspective": "topdown_34",
        "compose": [640, 360],
        "output": [1920, 1080],
        "upscale": 3,
        "grid": 32,
        "tile_size": 32,
        "nearest": True,
        "style": "pixel_32",
        "scale_mode": "native",
        "budgets": {
            "characters": 4,
            "creatures": 5,
            "props": 10,
            "vfx": 1,
            "buildings": 3,
            "foliage": 6,
        },
        "hud": dict(HUD_DOCKS),
        "layer_cap": 200,
    },
    "topdown_shooter": {
        "genre": "sci-fi top-down shooter / strategy",
        "perspective": "topdown",
        "compose": [1920, 1080],
        "output": [1920, 1080],
        "upscale": 1,
        "grid": 64,
        "tile_size": 256,
        "nearest": False,
        "style": "dark_scifi",
        "scale_mode": "target",
        "target_px": {
            "characters": 210,
            "creatures": 120,
            "enemies": 120,
            "props": 110,
            "vehicles": 160,
            "foliage": 180,
            "buildings": 280,
            "furniture": 130,
            "vfx": 90,
            "decals": 80,
            "terrain": 256,
            "tiles": 256,
        },
        "target_px_subject": {"vehicles/air": 150},
        "budgets": {
            "characters": 3,
            "creatures": 2,
            "enemies": 4,
            "props": 8,
            "vfx": 1,
            "buildings": 1,
            "vehicles": 2,
        },
        "hud": dict(HUD_DOCKS),
        "layer_cap": 200,
    },
    "dungeon_crawler": {
        "genre": "fantasy dungeon crawler",
        "perspective": "topdown_34",
        "compose": [1920, 1080],
        "output": [1920, 1080],
        "upscale": 1,
        "grid": 64,
        "tile_size": 256,
        "nearest": False,
        "style": "hand_painted_fantasy",
        "scale_mode": "target",
        "target_px": {
            "characters": 220,
            "creatures": 130,
            "enemies": 200,
            "props": 120,
            "vehicles": 160,
            "foliage": 200,
            "buildings": 280,
            "furniture": 150,
            "vfx": 90,
            "decals": 90,
        },
        "budgets": {
            "characters": 3,
            "enemies": 4,
            "props": 10,
            "vfx": 3,
            "foliage": 4,
        },
        "hud": dict(HUD_DOCKS),
        "layer_cap": 200,
        "single_ground_plane": True,
        "notes": (
            "Do not composite a perspective-painted hall behind an orthographic "
            "tile floor. Use one ground plane."
        ),
    },
    "side_platformer": {
        "genre": "side-scrolling platformer",
        "perspective": "side",
        "compose": [1920, 1080],
        "output": [1920, 1080],
        "upscale": 1,
        "grid": 64,
        "tile_size": 256,
        "nearest": False,
        "style": "flat_vector_ui",
        "scale_mode": "target",
        "target_px": {
            "characters": 200,
            "creatures": 90,
            "enemies": 90,
            "props": 80,
            "foliage": 220,
            "vfx": 70,
        },
        "budgets": {
            "characters": 2,
            "enemies": 4,
            "props": 8,
            "vfx": 2,
            "foliage": 10,
        },
        "hud": dict(HUD_DOCKS),
        "layer_cap": 200,
    },
}
