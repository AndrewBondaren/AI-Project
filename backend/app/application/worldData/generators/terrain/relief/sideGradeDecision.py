"""Explain SLOPE/SHEER (+ uphill facing) — tz_terrain_relief § Logging R8."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.facing import uphill_facing_toward
from app.application.worldData.generators.terrain.relief.profiles import (
    profile_side_fraction,
    sheer_band_m,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.specs import ReliefSideSpec


@dataclass(frozen=True)
class ReliefGradeDecision:
    """One cell/point grade decision — for logs, stamp, diagnostics."""

    kind: ReliefSideKind
    sector_index: int
    t: float
    fraction: float
    reason: str
    facing: Facing | None
    """Uphill cardinal, or None when SHEER / flat."""


def format_sides_summary(sides: list[ReliefSideSpec]) -> str:
    """INFO-line: side index → kind (+ sheer band)."""
    parts: list[str] = []
    for i, side in enumerate(sides):
        if side.kind == ReliefSideKind.SHEER:
            parts.append(f"{i}=SHEER(band_light={int(side.sheer_band_light)})")
        else:
            parts.append(f"{i}=SLOPE")
    return "[" + ", ".join(parts) + "]"


def decide_radial_grade(
    *,
    side: ReliefSideSpec,
    sector_index: int,
    t: float,
    dist_origin: float,
    outer_m: float,
    light_m: float,
    px: float,
    py: float,
    origin_x: float,
    origin_y: float,
) -> ReliefGradeDecision:
    """Profile + reason/facing for a radial (peak) ownership point."""
    frac = profile_side_fraction(
        side,
        t=t,
        dist_for_sheer=dist_origin,
        outer_m=outer_m,
        light_m=light_m,
    )
    kind = side.kind
    if kind == ReliefSideKind.SHEER:
        band = sheer_band_m(
            sheer_band_light=int(side.sheer_band_light),
            light_m=light_m,
        )
        threshold = outer_m - band
        inside = dist_origin < threshold
        reason = (
            f"nearest_sector={sector_index} side.kind=SHEER "
            f"dist_origin={dist_origin:.1f} outer={outer_m:.1f} band={band:.1f} "
            f"threshold={threshold:.1f} step={'1' if inside else '0'} "
            f"(отвес: grade-проход нет)"
        )
        facing = None
    else:
        reason = (
            f"nearest_sector={sector_index} side.kind=SLOPE "
            f"t={t:.3f} profile=smoothstep frac={frac:.3f} "
            f"(склон: uphill к origin)"
        )
        facing = uphill_facing_toward(px, py, origin_x, origin_y)
    return ReliefGradeDecision(
        kind=kind,
        sector_index=int(sector_index),
        t=float(t),
        fraction=float(frac),
        reason=reason,
        facing=facing,
    )


def plateau_hat_decision() -> ReliefGradeDecision:
    return ReliefGradeDecision(
        kind=ReliefSideKind.SLOPE,
        sector_index=-1,
        t=0.0,
        fraction=1.0,
        reason="plateau_hat dist_origin<=hat_radius fraction=1 (no side ownership)",
        facing=None,
    )
