"""SideFill — per-side height fractions (tz_map_light_bake § Mountain)."""

from __future__ import annotations

import math

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


def _sheer_fraction(
    *,
    dist_origin: float,
    radius_m: float,
    sheer_band_light: int,
    light_m: float,
) -> float:
    """Q7: ε band = ``sheer_band_light * light_m`` meters from outer radius."""
    band_m = max(0, int(sheer_band_light)) * max(1.0, float(light_m))
    if dist_origin < float(radius_m) - band_m:
        return 1.0
    return 0.0


def _slope_fraction(t: float) -> float:
    return 1.0 - _smoothstep(0.0, 1.0, max(0.0, min(1.0, t)))


def side_fill_fractions(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    cells: frozenset[LightCellRef],
    scale: LightGridScale,
) -> dict[LightCellRef, float]:
    """Ownership B (nearest edge) + per-side profile → fraction map."""
    if len(sides) != len(geometry.sectors):
        raise ValueError(
            f"sides length {len(sides)} != sectors {len(geometry.sectors)}"
        )
    ox, oy = geometry.origin_m
    radius = max(1e-6, geometry.radius_m)
    hat_r = geometry.hat_radius_m
    light_m = float(scale.light_m)
    out: dict[LightCellRef, float] = {}
    for ref in cells:
        cx, cy = light_cell_center_m(ref.gx, ref.gy, ref.tx, ref.ty, scale)
        px, py = float(cx), float(cy)
        dist_origin = math.hypot(px - ox, py - oy)
        if hat_r is not None and dist_origin <= hat_r:
            out[ref] = 1.0
            continue
        sector = _nearest_sector(px, py, geometry.sectors)
        side = sides[sector.index]
        if side.kind == MountainSideKind.SHEER:
            out[ref] = _sheer_fraction(
                dist_origin=dist_origin,
                radius_m=radius,
                sheer_band_light=int(side.sheer_band_light),
                light_m=light_m,
            )
            continue
        t = dist_origin / radius
        if hat_r is not None and hat_r < radius:
            t = max(0.0, (dist_origin - hat_r) / (radius - hat_r))
        out[ref] = _slope_fraction(t)
    return out
