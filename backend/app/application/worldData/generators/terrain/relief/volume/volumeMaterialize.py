"""Pure ribbon volume plan (SLOPE ramp / SHEER face) — tz_terrain_relief R36i §8b.

Light-grid v1 writes ``surface_z`` (+ facing in caller). Vertical solid fill
(N_eff / 3D column) is ensure-semantics for later skeleton; SHEER columns use
``surface_z`` at face top (``max(z_road, z_road+sign*h)``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.geom.geomResolve import (
    ResolvedGeom,
    geom_resolve,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind


@dataclass(frozen=True, slots=True)
class RibbonColumnPlan:
    """One outward column; ``k`` is 1..L (seed adjacent to road = 1)."""

    k: int
    surface_z: int


@dataclass(frozen=True, slots=True)
class RibbonVolumePlan:
    kind: ReliefSideKind
    h: int
    L: int
    angle_deg: float | None
    sign: int  # −1 slope_down / +1 slope_up
    columns: tuple[RibbonColumnPlan, ...]


def geom_for_cleared_length(
    *,
    h: int,
    kind: ReliefSideKind,
    length: int,
) -> ResolvedGeom:
    """Re-resolve after clearance shortened ``L`` (Geom-A with forced length)."""
    L = max(0, int(length))
    if L < 1:
        return ResolvedGeom(kind=kind, h=abs(int(h)), L=0, angle_deg=None, steps=())
    return geom_resolve(h=h, kind=kind, slope_length_cells=L)


def plan_ribbon_volume(
    *,
    z_road: int,
    h: int,
    sign: int,
    geom: ResolvedGeom,
) -> RibbonVolumePlan:
    """Build per-column ``surface_z`` for ``geom.L`` steps outward.

    ``sign``: −1 road higher than far side (slope_down); +1 far side higher.
    Invariant SLOPE: final z == ``z_road + sign * h``; ``sum(steps) == h``.
    """
    kind = geom.kind
    h_i = abs(int(h))
    z0 = int(z_road)
    s = -1 if int(sign) < 0 else 1
    L = int(geom.L)

    if L < 1 or h_i < 1:
        return RibbonVolumePlan(
            kind=kind, h=h_i, L=max(0, L), angle_deg=geom.angle_deg, sign=s, columns=(),
        )

    if kind is ReliefSideKind.SHEER:
        z_top = max(z0, z0 + s * h_i)
        cols = tuple(RibbonColumnPlan(k=k, surface_z=z_top) for k in range(1, L + 1))
        return RibbonVolumePlan(
            kind=kind, h=h_i, L=L, angle_deg=geom.angle_deg, sign=s, columns=cols,
        )

    steps = geom.steps
    if len(steps) != L or sum(steps) != h_i:
        raise ValueError(
            f"SLOPE geom steps mismatch: L={L} h={h_i} steps={steps}"
        )
    z = z0
    cols_list: list[RibbonColumnPlan] = []
    for k, step in enumerate(steps, start=1):
        z = z + s * int(step)
        cols_list.append(RibbonColumnPlan(k=k, surface_z=z))
    if z != z0 + s * h_i:
        raise ValueError(
            f"SLOPE volume did not close delta: z={z} expected={z0 + s * h_i}"
        )
    return RibbonVolumePlan(
        kind=kind,
        h=h_i,
        L=L,
        angle_deg=geom.angle_deg,
        sign=s,
        columns=tuple(cols_list),
    )


def ribbon_sign_from_dz(dz: int) -> int:
    """``relief_dz`` > 0 → slope_down (sign −1); < 0 → slope_up (+1)."""
    return -1 if int(dz) > 0 else 1


def plan_seed_volume(
    *,
    decision_geom: ResolvedGeom | None,
    h: int,
    kind: ReliefSideKind,
    L_eff: int,
    z_road: int,
    sign: int,
) -> RibbonVolumePlan | None:
    """Reuse decision geom when it matches clearance ``L_eff``; else re-resolve."""
    if (
        decision_geom is not None
        and decision_geom.kind is kind
        and int(decision_geom.L) == int(L_eff)
        and int(decision_geom.h) == int(h)
    ):
        geom = decision_geom
    else:
        geom = geom_for_cleared_length(h=h, kind=kind, length=L_eff)
    if geom.L < 1:
        return None
    return plan_ribbon_volume(z_road=z_road, h=h, sign=sign, geom=geom)
