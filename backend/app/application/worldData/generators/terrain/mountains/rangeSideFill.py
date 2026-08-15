"""Range SideFill — left/right laterals + optional end caps (tz_map_light_bake § Range)."""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

from app.application.worldData.generators.terrain.mountains.geom import (
    dist_point_to_polyline_m,
    dist_point_to_segment_m,
    nearest_point_on_polyline_m,
)
from app.application.worldData.generators.terrain.relief.geom.facing import (
    facing_wire,
    uphill_facing_toward,
)
from app.application.worldData.generators.terrain.relief.geom.profiles import (
    profile_side_fraction,
    sheer_band_m,
    sheer_fraction_lateral,
    slope_fraction,
)
from app.dataModel.spatial.facing import Facing
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


@dataclass(frozen=True)
class RangeSideGrade:
    fraction: float
    facing: Facing | None
    side: MountainSideSpec


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy) or 1.0
    return dx / length, dy / length


def _perp_left(dx: float, dy: float) -> tuple[float, float]:
    return _unit(-dy, dx)


def _cap_edge(
    endpoint: tuple[float, float],
    tangent_out: tuple[float, float],
    half_width: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
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
    edges: list[tuple[_Owner, tuple[float, float], tuple[float, float], MountainSideSpec]] = []
    for i in range(len(spine) - 1):
        ax, ay = float(spine[i][0]), float(spine[i][1])
        bx, by = float(spine[i + 1][0]), float(spine[i + 1][1])
        dx, dy = bx - ax, by - ay
        lx, ly = _perp_left(dx, dy)
        edges.append((
            _Owner.LEFT,
            (ax + lx * half_width, ay + ly * half_width),
            (bx + lx * half_width, by + ly * half_width),
            sides.left,
        ))
        edges.append((
            _Owner.RIGHT,
            (ax - lx * half_width, ay - ly * half_width),
            (bx - lx * half_width, by - ly * half_width),
            sides.right,
        ))
    if sides.start is not None and len(spine) >= 2:
        p0 = (float(spine[0][0]), float(spine[0][1]))
        p1 = (float(spine[1][0]), float(spine[1][1]))
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


def range_side_grade_at_xy(
    px: float,
    py: float,
    *,
    spine: list[tuple[int, int]],
    half_width_m: float,
    sides: MountainRangeSides,
    light_m: float,
) -> RangeSideGrade | None:
    """Fraction + facing at point, or None if outside corridor.

    SLOPE: uphill facing toward nearest spine point; SHEER: facing=None.
    """
    half = max(1e-6, float(half_width_m))
    dist = dist_point_to_polyline_m(px, py, spine)
    if dist > half:
        return None
    edges = _range_edges(spine, half, sides)
    if not edges:
        nearest = nearest_point_on_polyline_m(px, py, spine)
        facing = (
            uphill_facing_toward(px, py, nearest[0], nearest[1])
            if nearest is not None
            else None
        )
        return RangeSideGrade(
            fraction=slope_fraction(dist / half),
            facing=facing,
            side=MountainSideSpec(kind=MountainSideKind.SLOPE),
        )
    best_side = edges[0][3]
    best_d = float("inf")
    for _owner, a, b, side in edges:
        d = dist_point_to_segment_m(px, py, a, b)
        if d < best_d:
            best_d = d
            best_side = side
    t = dist / half
    if best_side.kind == MountainSideKind.SHEER:
        band = sheer_band_m(
            sheer_band_light=int(best_side.sheer_band_light),
            light_m=light_m,
        )
        frac = sheer_fraction_lateral(
            dist_spine=dist, half_width_m=half, band_m=band,
        )
        return RangeSideGrade(fraction=frac, facing=None, side=best_side)
    frac = profile_side_fraction(
        best_side,
        t=t,
        dist_for_sheer=dist,
        outer_m=half,
        light_m=light_m,
    )
    nearest = nearest_point_on_polyline_m(px, py, spine)
    facing = (
        uphill_facing_toward(px, py, nearest[0], nearest[1])
        if nearest is not None
        else None
    )
    return RangeSideGrade(fraction=frac, facing=facing, side=best_side)


def range_side_fraction_at_xy(
    px: float,
    py: float,
    *,
    spine: list[tuple[int, int]],
    half_width_m: float,
    sides: MountainRangeSides,
    light_m: float,
) -> float | None:
    grade = range_side_grade_at_xy(
        px, py, spine=spine, half_width_m=half_width_m, sides=sides, light_m=light_m,
    )
    return None if grade is None else grade.fraction


def range_side_fill_at_points(
    spec: MountainRangeSpec,
    points: Iterable[tuple[KeyT, float, float]],
    *,
    light_m: float,
) -> dict[KeyT, float]:
    """Corridor occupancy + left/right/caps SideFill → fraction map (no peaks)."""
    grades = range_side_grades_at_points(spec, points, light_m=light_m)
    return {k: g.fraction for k, g in grades.items()}


def range_side_grades_at_points(
    spec: MountainRangeSpec,
    points: Iterable[tuple[KeyT, float, float]],
    *,
    light_m: float,
) -> dict[KeyT, RangeSideGrade]:
    half = max(1, int(spec.width_m)) / 2.0
    spine = list(spec.spine)
    sides = spec.sides
    out: dict[KeyT, RangeSideGrade] = {}
    for key, px, py in points:
        grade = range_side_grade_at_xy(
            float(px),
            float(py),
            spine=spine,
            half_width_m=half,
            sides=sides,
            light_m=light_m,
        )
        if grade is not None:
            out[key] = grade
    return out


def range_facing_wire_map(
    grades: dict[KeyT, RangeSideGrade],
) -> dict[KeyT, str | None]:
    return {k: facing_wire(g.facing) for k, g in grades.items()}
