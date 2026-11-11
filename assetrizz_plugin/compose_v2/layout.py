"""Feet/top-left conversion, band defaults, and y-sorted world z."""

from __future__ import annotations

from .assets import Metrics
from .bands import BANDS, CATEGORY_BAND

Y_SORTED_BANDS = frozenset({"world", "aerial"})
AERIAL_SUBCATEGORIES = frozenset({"air", "aerial", "flying"})


def feet_from_topleft(
    metrics: Metrics,
    x: int | float,
    y: int | float,
    scale: float,
    flip_x: bool = False,
) -> tuple[float, float]:
    """Convert a layer's top-left corner to its pivot (feet) point."""
    pivot_x, pivot_y = metrics.pivot
    if flip_x:
        pivot_x = 1.0 - pivot_x
    return (
        float(x) + scale * metrics.width * pivot_x,
        float(y) + scale * metrics.height * pivot_y,
    )


def topleft_from_feet(
    metrics: Metrics,
    feet_x: float,
    feet_y: float,
    scale: float,
    flip_x: bool = False,
) -> tuple[int, int]:
    """Convert a pivot (feet) point back to a rounded top-left corner."""
    pivot_x, pivot_y = metrics.pivot
    if flip_x:
        pivot_x = 1.0 - pivot_x
    return (
        int(round(feet_x - scale * metrics.width * pivot_x)),
        int(round(feet_y - scale * metrics.height * pivot_y)),
    )


def band_z(band: str, feet_y: float = 0.0) -> int:
    """Return a layer z for ``band``; y-sorted bands add the feet y."""
    if band not in BANDS:
        raise ValueError(f"unknown band: {band!r}")
    base = BANDS[band]
    if band in Y_SORTED_BANDS:
        return base + int(round(float(feet_y)))
    return base


def default_band(
    metrics: Metrics,
    explicit: str | None = None,
    *,
    flying: bool = False,
) -> str:
    """Pick a band from an explicit choice, aerial flags, or catalog category."""
    if explicit:
        if explicit not in BANDS:
            raise ValueError(f"unknown band: {explicit!r}")
        return explicit
    if flying:
        return "aerial"
    if metrics.subcategory in AERIAL_SUBCATEGORIES:
        return "aerial"
    return CATEGORY_BAND.get(metrics.category, "world")
