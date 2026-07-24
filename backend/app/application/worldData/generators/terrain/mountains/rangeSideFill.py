"""Range SideFill — left/right laterals + optional end caps (tz_map_light_bake § Range)."""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from enum import Enum
from typing import TypeVar

from app.application.worldData.generators.terrain.mountains.geom import (
    dist_point_to_polyline_m,
    dist_point_to_segment_m,
)
from app.application.worldData.generators.terrain.mountains.sideFill import (
    profile_side_fraction,
    sheer_band_m,
    sheer_fraction_lateral,
    slope_fraction,
)
from app.dataModel.terrainMasks.mountain.enums import MountainSideKind
from app.dataModel.terrainMasks.mountain.specs import (
    MountainRangeSides,
    MountainRangeSpec,
    MountainSideSpec,
)

KeyT = TypeVar("KeyT", bound=Hashable)


class _Owner(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    START = "start"
    END = "end"


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def _perp_left(dx: float, dy: float) -> tuple[float, float]:
    # left normal of direction (dx, dy)
    return _unit(-dy, dx)


def _cap_edge(
    endpoint: tuple[float, float],
    tangent_out: tuple[float, float],
    half_width: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """End-cap edge: perpendicular through endpoint, length = width."""
    nx, ny = _perp_left(tangent_out[0], tangent_out[1])
    ex, ey = endpoint
    a = (ex - nx * half_width, ey - ny * half_width)
    b = (ex + nx * half_width, ey + ny * half_width)
    return a, b


def _range_edges(
    spine: list[tuple[int, int]],
    half_width: float,
    sides: MountainRangeSides,
) -> list[tuple[_Owner, tuple[float, float], tuple[float, float], MountainSideSpec]]:
    """Boundary edges for ownership B: left/right along spine + optional caps."""
    edges: list[tuple[_Owner, tuple[float, float], tuple[float, float], MountainSideSpec]] = []
    for i in range(len(spine) - 1):
        ax, ay = float(spine[i][0]), float(spine[i][1])
        bx, by = float(spine[i + 1][0]), float(spine[i + 1][1])
        dx, dy = bx - ax, by - ay
        lx, ly = _perp_left(dx, dy)
        # left boundary (outward +left normal)
        edges.append((
            _Owner.LEFT,
            (ax + lx * half_width, ay + ly * half_width),
            (bx + lx * half_width, by + ly * half_width),
            sides.left,
        ))
        # right boundary (outward −left = right)
        edges.append((
            _Owner.RIGHT,
            (ax - lx * half_width, ay - ly * half_width),
            (bx - lx * half_width, by - ly * half_width),
            sides.right,
        ))
    if sides.start is not None and len(spine) >= 2:
        p0 = (float(spine[0][0]), float(spine[0][1]))
        p1 = (float(spine[1][0]), float(spine[1][1]))
        # outward tangent at start = opposite of first segment direction
        tx, ty = _unit(p0[0] - p1[0], p0[1] - p1[1])
        a, b = _cap_edge(p0, (tx, ty), half_width)
        edges.append((_Owner.START, a, b, sides.start))
    if sides.end is not None and len(spine) >= 2:
        p_a = (float(spine[-2][0]), float(spine[-2][1]))
        p_b = (float(spine[-1][0]), float(spine[-1][1]))
        tx, ty = _unit(p_b[0] - p_a[0], p_b[1] - p_a[1])
        a, b = _cap_edge(p_b, (tx, ty), half_width)
        edges.append((_Owner.END, a, b, sides.end))
    return edges


def range_side_fraction_at_xy(
    px: float,
    py: float,
    *,
    spine: list[tuple[int, int]],
    half_width_m: float,
    sides: MountainRangeSides,
    light_m: float,
) -> float | None:
    """Fraction at point, or None if outside corridor."""
    half = max(1e-6, float(half_width_m))
    dist = dist_point_to_polyline_m(px, py, spine)
    if dist > half:
        return None
    edges = _range_edges(spine, half, sides)
    if not edges:
        return slope_fraction(dist / half)
    best_owner = edges[0][0]
    best_side = edges[0][3]
    best_d = float("inf")
    for owner, a, b, side in edges:
        d = dist_point_to_segment_m(px, py, a, b)
        if d < best_d:
            best_d = d
            best_owner = owner
            best_side = side
    del best_owner  # ownership selects side only
    t = dist / half
    if best_side.kind == MountainSideKind.SHEER:
        band = sheer_band_m(
            sheer_band_light=int(best_side.sheer_band_light),
            light_m=light_m,
        )
        return sheer_fraction_lateral(
            dist_spine=dist, half_width_m=half, band_m=band,
        )
    return profile_side_fraction(
        best_side,
        t=t,
        dist_for_sheer=dist,
        outer_m=half,
        light_m=light_m,
    )


def range_side_fill_at_points(
    spec: MountainRangeSpec,
    points: Iterable[tuple[KeyT, float, float]],
    *,
    light_m: float,
) -> dict[KeyT, float]:
    """Corridor occupancy + left/right/caps SideFill → fraction map (no peaks)."""
    half = max(1, int(spec.width_m)) / 2.0
    spine = list(spec.spine)
    sides = spec.sides
    out: dict[KeyT, float] = {}
    for key, px, py in points:
        frac = range_side_fraction_at_xy(
            float(px),
            float(py),
            spine=spine,
            half_width_m=half,
            sides=sides,
            light_m=light_m,
        )
        if frac is not None:
            out[key] = frac
    return out
