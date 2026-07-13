"""DEBT-7 / WP-16: path heading for PLAYER_PATH corridor."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from app.dataModel.worldPack.pathHeadingPolicy import PathHeadingPolicy


class _RectLike(Protocol):
    x_min: int
    x_max: int
    y_min: int
    y_max: int


@dataclass(frozen=True)
class PathHeading:
    dx: int
    dy: int

    @property
    def is_defined(self) -> bool:
        return self.dx != 0 or self.dy != 0

    def unit(self) -> tuple[float, float]:
        length = math.hypot(self.dx, self.dy)
        if length == 0:
            return 0.0, 0.0
        return self.dx / length, self.dy / length


def quantize_heading(dx: int, dy: int) -> PathHeading | None:
    if dx == 0 and dy == 0:
        return None

    def _sign(value: int) -> int:
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    return PathHeading(dx=_sign(dx), dy=_sign(dy))


def heading_from_positions(
    positions: list[tuple[int, int]],
    *,
    max_samples: int | None = None,
) -> PathHeading | None:
    """Fallback (WP-16 b): vector from oldest→newest of recent positions."""
    if len(positions) < 2:
        return None
    limit = max_samples if max_samples is not None else PathHeadingPolicy.canonical_defaults().position_history_max
    recent = positions[-limit:]
    x0, y0 = recent[0]
    x1, y1 = recent[-1]
    return quantize_heading(x1 - x0, y1 - y0)


def resolve_path_heading(
    *,
    intent_dx: int | None = None,
    intent_dy: int | None = None,
    positions: list[tuple[int, int]] | None = None,
) -> PathHeading | None:
    """Intent overrides position history (WP-16)."""
    if intent_dx is not None or intent_dy is not None:
        heading = quantize_heading(intent_dx or 0, intent_dy or 0)
        if heading is not None:
            return heading
    if positions:
        return heading_from_positions(positions)
    return None


def macro_tiles_ahead(
    tile_gx: int,
    tile_gy: int,
    heading: PathHeading,
    depth_tiles: int,
) -> list[tuple[int, int]]:
    if depth_tiles <= 0 or not heading.is_defined:
        return []
    return [
        (tile_gx + heading.dx * step, tile_gy + heading.dy * step)
        for step in range(1, depth_tiles + 1)
    ]


def _clamp_int(value: float, lo: int, hi: int) -> int:
    return int(max(lo, min(value, hi)))


def predicted_border_entry(
    from_gx: int,
    from_gy: int,
    to_gx: int,
    to_gy: int,
    path_x: float,
    path_y: float,
    tile_size_m: int,
) -> tuple[int, int]:
    """Predicted entry into ``to`` tile at shared border with ``from`` (WP-13).

    Lateral axis keeps the path cross-track clamped into the destination tile bbox;
    along-track axis snaps to the shared edge inside ``to``.
    """
    if tile_size_m <= 0:
        raise ValueError("tile_size_m must be positive")
    dgx = to_gx - from_gx
    dgy = to_gy - from_gy
    x0 = to_gx * tile_size_m
    y0 = to_gy * tile_size_m
    x1 = x0 + tile_size_m - 1
    y1 = y0 + tile_size_m - 1

    if dgx > 0:
        entry_x = x0
    elif dgx < 0:
        entry_x = x1
    else:
        entry_x = _clamp_int(path_x, x0, x1)

    if dgy > 0:
        entry_y = y0
    elif dgy < 0:
        entry_y = y1
    else:
        entry_y = _clamp_int(path_y, y0, y1)

    if dgx != 0 and dgy == 0:
        entry_y = _clamp_int(path_y, y0, y1)
    elif dgy != 0 and dgx == 0:
        entry_x = _clamp_int(path_x, x0, x1)
    # diagonal: both axes already snapped to the inward corner facing ``from``

    return entry_x, entry_y


def chunk_center(rect: _RectLike) -> tuple[float, float]:
    return (rect.x_min + rect.x_max) / 2.0, (rect.y_min + rect.y_max) / 2.0


def chunk_in_path_corridor(
    center_x: float,
    center_y: float,
    anchor_x: float,
    anchor_y: float,
    heading: PathHeading,
    *,
    depth_m: float,
    half_width_m: float,
) -> bool:
    rel_x = center_x - anchor_x
    rel_y = center_y - anchor_y
    ux, uy = heading.unit()
    if ux == 0.0 and uy == 0.0:
        return False
    along = rel_x * ux + rel_y * uy
    if along < 0 or along > depth_m:
        return False
    lateral = abs(-uy * rel_x + ux * rel_y)
    return lateral <= half_width_m


def filter_corridor_rects(
    rects: list[_RectLike],
    anchor_x: float,
    anchor_y: float,
    heading: PathHeading,
    *,
    depth_m: float,
    half_width_m: float,
) -> list[_RectLike]:
    return [
        rect for rect in rects
        if chunk_in_path_corridor(
            *chunk_center(rect),
            anchor_x,
            anchor_y,
            heading,
            depth_m=depth_m,
            half_width_m=half_width_m,
        )
    ]
