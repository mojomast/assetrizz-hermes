"""Asset metrics, catalog pivots, and auto-scale for compose-v2.

Tests inject :class:`Metrics` (or build one from an asset mapping) so they do
not need the full local library. :func:`metrics` is the library-backed path
used in production; it resolves through ``assetrizz_plugin.library``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .bands import SKIP_SLUGS

DEFAULT_PIVOT: tuple[float, float] = (0.5, 1.0)
NATIVE_SCALE_MODES = frozenset({"native", "style", "style_native"})
MIN_AUTO_SCALE = 0.05
MAX_AUTO_SCALE = 8.0


def normalize_pivot(value: Any) -> tuple[float, float]:
    """Return an ``(x, y)`` pivot, defaulting to bottom-center."""
    if value is None:
        return DEFAULT_PIVOT
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return DEFAULT_PIVOT
    if isinstance(value, Mapping):
        raw_x = value.get("x", DEFAULT_PIVOT[0])
        raw_y = value.get("y", DEFAULT_PIVOT[1])
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        raw_x, raw_y = value[0], value[1]
    else:
        return DEFAULT_PIVOT
    try:
        return (float(raw_x), float(raw_y))
    except (TypeError, ValueError):
        return DEFAULT_PIVOT


@dataclass
class Metrics:
    """Dimensions and catalog metadata for one asset."""

    width: int
    height: int
    bbox: tuple[int, int, int, int] | None = None
    category: str = ""
    subcategory: str = ""
    slug: str = ""
    style: str = ""
    pivot: tuple[float, float] = DEFAULT_PIVOT
    tileable: bool = False
    path: str = ""

    def __post_init__(self) -> None:
        self.width = int(self.width)
        self.height = int(self.height)
        if self.bbox is None:
            self.bbox = (0, 0, self.width, self.height)
        else:
            self.bbox = tuple(int(v) for v in self.bbox)  # type: ignore[assignment]
        self.pivot = normalize_pivot(self.pivot)

    @property
    def vis_w(self) -> int:
        return max(0, self.bbox[2] - self.bbox[0])

    @property
    def vis_h(self) -> int:
        return max(0, self.bbox[3] - self.bbox[1])


def metrics_from_asset(
    asset: Mapping[str, Any],
    *,
    width: int | None = None,
    height: int | None = None,
    bbox: tuple[int, int, int, int] | None = None,
) -> Metrics:
    """Build metrics from a library asset mapping plus injected image facts."""
    raw_bbox = bbox
    if raw_bbox is not None:
        raw_bbox = tuple(int(v) for v in raw_bbox)  # type: ignore[assignment]
    width = int(width if width is not None else asset.get("width") or (raw_bbox[2] - raw_bbox[0] if raw_bbox else 1))
    height = int(height if height is not None else asset.get("height") or (raw_bbox[3] - raw_bbox[1] if raw_bbox else 1))
    return Metrics(
        width=width,
        height=height,
        bbox=raw_bbox,
        category=str(asset.get("category") or ""),
        subcategory=str(asset.get("subcategory") or ""),
        slug=str(asset.get("slug") or ""),
        style=str(asset.get("style_pack") or asset.get("style") or ""),
        pivot=normalize_pivot(asset.get("pivot")),
        tileable=bool(asset.get("tileable")),
        path=str(asset.get("path") or ""),
    )


def metrics(slug: str) -> Metrics:
    """Resolve one asset through the plugin library and measure its alpha bbox."""
    if slug in SKIP_SLUGS:
        raise RuntimeError(f"refusing skipped asset: {slug}")
    from assetrizz_plugin.library import resolve_asset

    asset = resolve_asset(slug=slug)
    from PIL import Image

    with Image.open(asset["file"]) as opened:
        image = opened.convert("RGBA")
        alpha = image.getchannel("A")
        bbox = alpha.getbbox() or (0, 0, image.width, image.height)
        width, height = image.size
    return metrics_from_asset(asset, width=width, height=height, bbox=bbox)


def full_slug(style: str, slug: str) -> str:
    """Expand a style-relative slug into a catalog slug."""
    style = (style or "").strip()
    slug = (slug or "").strip()
    if slug.startswith(style + "/"):
        return slug
    if "/" in slug:
        return f"{style}/{slug}"
    raise ValueError(f"slug must be style-prefixed or a path under the style: {slug!r}")


def target_scale(
    metrics: Metrics,
    template: Mapping[str, Any],
    override: float | None = None,
) -> float:
    """Return an auto-scale for ``metrics`` under a template-like mapping."""
    if override is not None:
        return float(override)
    mode = str(template.get("scale_mode") or "")
    if mode in NATIVE_SCALE_MODES:
        return 1.0
    key = f"{metrics.category}/{metrics.subcategory}" if metrics.subcategory else metrics.category
    subject_targets = template.get("target_px_subject") or {}
    category_targets = template.get("target_px") or {}
    target = subject_targets.get(key)
    if target is None:
        target = category_targets.get(key)
    if target is None:
        target = category_targets.get(metrics.category)
    if not target:
        return 1.0
    visible_height = max(1, metrics.vis_h)
    scale = float(target) / visible_height
    return max(MIN_AUTO_SCALE, min(MAX_AUTO_SCALE, scale))
