"""Explain SLOPE/SHEER (+ uphill facing hint) — tz_terrain_relief § Logging.

Adapter under mountains/ until relief module extract (R6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.application.worldData.generators.terrain.mountains.formGeometry import (
    MountainFormGeometry,
    SideSector,
)
from app.application.worldData.generators.terrain.mountains.geom import (
    dist_point_to_segment_m,
)
from app.application.worldData.generators.terrain.mountains.sideFill import (
    profile_side_fraction,
    sheer_band_m,
)
from app.dataModel.terrainMasks.mountain.enums import MountainSideKind
from app.dataModel.terrainMasks.mountain.specs import MountainSideSpec

_CARDINALS = ("east", "west", "north", "south")


@dataclass(frozen=True)
class SideGradeDecision:
    """One cell/point grade decision — for logs and diagnostics."""

    kind: MountainSideKind
    sector_index: int
    t: float
    fraction: float
    reason: str
    facing: str | None
    """Uphill cardinal, or None when SHEER / flat."""


def _nearest_sector(px: float, py: float, sectors: tuple[SideSector, ...]) -> SideSector:
    best = sectors[0]
    best_d = float("inf")
    for sec in sectors:
        d = dist_point_to_segment_m(px, py, sec.edge[0], sec.edge[1])
        if d < best_d:
            best_d = d
            best = sec
    return best


def uphill_facing_toward(
    px: float,
    py: float,
    target_x: float,
    target_y: float,
) -> str | None:
    """Cardinal toward ``target`` (uphill for radial slope → mountain origin)."""
    dx = float(target_x) - float(px)
    dy = float(target_y) - float(py)
    if dx == 0.0 and dy == 0.0:
        return None
    if abs(dx) >= abs(dy):
        return "east" if dx > 0.0 else "west"
    return "north" if dy > 0.0 else "south"


def explain_side_grade_at_xy(
    geometry: MountainFormGeometry,
    sides: list[MountainSideSpec],
    px: float,
    py: float,
    *,
    light_m: float,
) -> SideGradeDecision:
    """Ownership B + profile — same math as ``side_fill_fraction_at_xy``, with reason."""
    if len(sides) != len(geometry.sectors):
        raise ValueError(
            f"sides length {len(sides)} != sectors {len(geometry.sectors)}"
        )
    ox, oy = geometry.origin_m
    radius = max(1e-6, geometry.radius_m)
    hat_r = geometry.hat_radius_m
    dist_origin = math.hypot(px - ox, py - oy)
    if hat_r is not None and dist_origin <= hat_r:
        return SideGradeDecision(
            kind=MountainSideKind.SLOPE,
            sector_index=-1,
            t=0.0,
            fraction=1.0,
            reason="plateau_hat dist_origin<=hat_radius fraction=1 (no side ownership)",
            facing=None,
        )
    sector = _nearest_sector(px, py, geometry.sectors)
    side = sides[sector.index]
    t = dist_origin / radius
    if hat_r is not None and hat_r < radius:
        t = max(0.0, (dist_origin - hat_r) / (radius - hat_r))
    frac = profile_side_fraction(
        side,
        t=t,
        dist_for_sheer=dist_origin,
        outer_m=radius,
        light_m=light_m,
    )
    kind = side.kind
    if kind == MountainSideKind.SHEER:
        band = sheer_band_m(
            sheer_band_light=int(side.sheer_band_light),
            light_m=light_m,
        )
        threshold = radius - band
        inside = dist_origin < threshold
        reason = (
            f"nearest_sector={sector.index} side.kind=SHEER "
            f"dist_origin={dist_origin:.1f} outer={radius:.1f} band={band:.1f} "
            f"threshold={threshold:.1f} step={'1' if inside else '0'} "
            f"(отвес: grade-проход нет)"
        )
        facing = None
    else:
        reason = (
            f"nearest_sector={sector.index} side.kind=SLOPE "
            f"t={t:.3f} profile=smoothstep frac={frac:.3f} "
            f"(склон: uphill к origin)"
        )
        facing = uphill_facing_toward(px, py, ox, oy)
        if facing is not None and facing not in _CARDINALS:
            facing = None
    return SideGradeDecision(
        kind=kind,
        sector_index=int(sector.index),
        t=float(t),
        fraction=float(frac),
        reason=reason,
        facing=facing,
    )


def format_sides_summary(sides: list[MountainSideSpec]) -> str:
    """INFO-line: side index → kind (+ sheer band)."""
    parts: list[str] = []
    for i, side in enumerate(sides):
        if side.kind == MountainSideKind.SHEER:
            parts.append(f"{i}=SHEER(band_light={int(side.sheer_band_light)})")
        else:
            parts.append(f"{i}=SLOPE")
    return "[" + ", ".join(parts) + "]"
