"""SideFill — per-side height fractions (tz_map_light_bake § Mountain).

Profiles live in ``terrain/relief``; this module owns FormGeometry ownership B.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from typing import TypeVar

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    MountainFormGeometry,
    SideSector,
)
from app.application.worldData.generators.terrain.mountains.geom import (
    dist_point_to_segment_m,
)
from app.application.worldData.generators.terrain.relief.facing import uphill_facing_toward
from app.application.worldData.generators.terrain.relief.profiles import (
    profile_side_fraction,
    sheer_band_m,
    sheer_fraction_lateral,
    sheer_fraction_radial,
    slope_fraction,
)
from app.application.worldData.generators.terrain.relief.sideGradeDecision import (
    ReliefGradeDecision,
    decide_radial_grade,
    plateau_hat_decision,
)
from app.application.worldData.masks.footprint import LightCellRef
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_cell_center_m,
)
from app.dataModel.terrainMasks.mountain.specs import MountainSideSpec

KeyT = TypeVar("KeyT", bound=Hashable)

__all__ = [
    "profile_side_fraction",
    "sheer_band_m",
    "sheer_fraction_lateral",
    "sheer_fraction_radial",
    "side_fill_fraction_at_xy",
    "side_fill_fractions",
    "side_fill_fractions_at_points",
    "side_fill_grade_at_xy",
    "slope_fraction",
    "uphill_facing_toward",
]


def _nearest_sector(px: float, py: float, sectors: tuple[SideSector, ...]) -> SideSector:
    best = sectors[0]
    best_d = float("inf")
    for sec in sectors:
        d = dist_point_to_segment_m(px, py, sec.edge[0], sec.edge[1])
        if d < best_d:
            best_d = d
            best = sec
    return best


def side_fill_fraction_at_xy(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    px: float,
    py: float,
    *,
    light_m: float,
) -> float:
    """Ownership B (nearest edge) + per-side profile at one point (meters)."""
    return side_fill_grade_at_xy(geometry, sides, px, py, light_m=light_m).fraction


def side_fill_grade_at_xy(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    px: float,
    py: float,
    *,
    light_m: float,
) -> ReliefGradeDecision:
    """Ownership B + profile + facing — used for stamp and R8 logs."""
    if len(sides) != len(geometry.sectors):
        raise ValueError(
            f"sides length {len(sides)} != sectors {len(geometry.sectors)}"
        )
    ox, oy = geometry.origin_m
    radius = max(1e-6, geometry.radius_m)
    hat_r = geometry.hat_radius_m
    dist_origin = math.hypot(px - ox, py - oy)
    if hat_r is not None and dist_origin <= hat_r:
        return plateau_hat_decision()
    sector = _nearest_sector(px, py, geometry.sectors)
    side = sides[sector.index]
    t = dist_origin / radius
    if hat_r is not None and hat_r < radius:
        t = max(0.0, (dist_origin - hat_r) / (radius - hat_r))
    return decide_radial_grade(
        side=side,
        sector_index=int(sector.index),
        t=t,
        dist_origin=dist_origin,
        outer_m=radius,
        light_m=light_m,
        px=px,
        py=py,
        origin_x=float(ox),
        origin_y=float(oy),
    )


def side_fill_fractions_at_points(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    points: Iterable[tuple[KeyT, float, float]],
    *,
    light_m: float,
) -> dict[KeyT, float]:
    """``points``: (key, x_m, y_m) → fraction map."""
    out: dict[KeyT, float] = {}
    for key, px, py in points:
        out[key] = side_fill_fraction_at_xy(
            geometry, sides, float(px), float(py), light_m=light_m,
        )
    return out


def side_fill_grades_at_points(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    points: Iterable[tuple[KeyT, float, float]],
    *,
    light_m: float,
) -> dict[KeyT, ReliefGradeDecision]:
    out: dict[KeyT, ReliefGradeDecision] = {}
    for key, px, py in points:
        out[key] = side_fill_grade_at_xy(
            geometry, sides, float(px), float(py), light_m=light_m,
        )
    return out


def side_fill_fractions(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    cells: frozenset[LightCellRef],
    scale: LightGridScale,
) -> dict[LightCellRef, float]:
    """Light-grid wrapper around ``side_fill_fractions_at_points``."""
    points = (
        (ref, *light_cell_center_m(ref.gx, ref.gy, ref.tx, ref.ty, scale))
        for ref in cells
    )
    return side_fill_fractions_at_points(
        geometry, sides, points, light_m=float(scale.light_m),
    )


def side_fill_grades(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    cells: frozenset[LightCellRef],
    scale: LightGridScale,
) -> dict[LightCellRef, ReliefGradeDecision]:
    points = (
        (ref, *light_cell_center_m(ref.gx, ref.gy, ref.tx, ref.ty, scale))
        for ref in cells
    )
    return side_fill_grades_at_points(
        geometry, sides, points, light_m=float(scale.light_m),
    )
