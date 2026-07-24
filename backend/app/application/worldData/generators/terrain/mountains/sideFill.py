"""SideFill — per-side height fractions (tz_map_light_bake § Mountain)."""

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
from app.application.worldData.masks.footprint import LightCellRef
from app.application.worldData.pack.bake.lightGrid.coords import (
    LightGridScale,
    light_cell_center_m,
)
from app.dataModel.terrainMasks.mountain.enums import MountainSideKind
from app.dataModel.terrainMasks.mountain.specs import MountainSideSpec

KeyT = TypeVar("KeyT", bound=Hashable)


def _nearest_sector(px: float, py: float, sectors: tuple[SideSector, ...]) -> SideSector:
    best = sectors[0]
    best_d = float("inf")
    for sec in sectors:
        d = dist_point_to_segment_m(px, py, sec.edge[0], sec.edge[1])
        if d < best_d:
            best_d = d
            best = sec
    return best


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def sheer_band_m(*, sheer_band_light: int, light_m: float) -> float:
    """ε band in meters — SoT: ``sheer_band_light * light_m`` (light + coarse)."""
    return max(0, int(sheer_band_light)) * max(1.0, float(light_m))


def sheer_fraction_radial(
    *,
    dist_origin: float,
    radius_m: float,
    band_m: float,
) -> float:
    """SHEER: 1 inside outer radius − band, else 0."""
    if dist_origin < float(radius_m) - max(0.0, float(band_m)):
        return 1.0
    return 0.0


def sheer_fraction_lateral(*, dist_spine: float, half_width_m: float, band_m: float) -> float:
    """SHEER on range lateral/cap: 1 until outer edge − band, else 0."""
    half = max(1e-6, float(half_width_m))
    if dist_spine < half - max(0.0, float(band_m)):
        return 1.0
    return 0.0


def slope_fraction(t: float) -> float:
    """SLOPE: smooth falloff ``1 − smoothstep(0,1,t)``."""
    return 1.0 - _smoothstep(0.0, 1.0, max(0.0, min(1.0, t)))


def profile_side_fraction(
    side: MountainSideSpec,
    *,
    t: float,
    dist_for_sheer: float,
    outer_m: float,
    light_m: float,
) -> float:
    """Apply SHEER/SLOPE profile. ``outer_m`` = radius (peak) or half_width (range)."""
    if side.kind == MountainSideKind.SHEER:
        band = sheer_band_m(
            sheer_band_light=int(side.sheer_band_light),
            light_m=light_m,
        )
        return sheer_fraction_radial(
            dist_origin=dist_for_sheer,
            radius_m=outer_m,
            band_m=band,
        )
    return slope_fraction(t)


def side_fill_fraction_at_xy(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    px: float,
    py: float,
    *,
    light_m: float,
) -> float:
    """Ownership B (nearest edge) + per-side profile at one point (meters)."""
    if len(sides) != len(geometry.sectors):
        raise ValueError(
            f"sides length {len(sides)} != sectors {len(geometry.sectors)}"
        )
    ox, oy = geometry.origin_m
    radius = max(1e-6, geometry.radius_m)
    hat_r = geometry.hat_radius_m
    dist_origin = math.hypot(px - ox, py - oy)
    if hat_r is not None and dist_origin <= hat_r:
        return 1.0
    sector = _nearest_sector(px, py, geometry.sectors)
    side = sides[sector.index]
    t = dist_origin / radius
    if hat_r is not None and hat_r < radius:
        t = max(0.0, (dist_origin - hat_r) / (radius - hat_r))
    return profile_side_fraction(
        side,
        t=t,
        dist_for_sheer=dist_origin,
        outer_m=radius,
        light_m=light_m,
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
