"""Geom-A|B resolve + ``partition_height`` — tz_terrain_relief R36 / §8a.

Pure: ``h=|dz|`` + knobs + kind → ``{h, L, angle_deg, kind, steps}``.
Geom-C (L+θ→h) is UI-only — not here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.reliefGradeKnobs import (
    DEFAULT_SLOPE_LENGTH_CELLS,
    resolved_slope_length_cells,
)


class GeomKnobs(Protocol):
    """Minimal knobs surface (POJO case/band or ``ReliefDeltaInterval``)."""

    slope_length_cells: int | None
    target_angle_deg: float | None


@dataclass(frozen=True, slots=True)
class ResolvedGeom:
    """Resolved triangle / sheer strip for one grade site."""

    kind: ReliefSideKind
    h: int
    L: int
    angle_deg: float | None  # None for SHEER
    steps: tuple[int, ...]  # SLOPE: sum == h; SHEER: empty


def partition_height(h: int, length: int) -> tuple[int, ...]:
    """Split ``h`` into ``length`` non-negative integer steps; ``sum == h``.

    Canon (R36i): ``q = h // L``, ``r = h % L``; first ``r`` steps = ``q+1``,
    rest = ``q``. When ``h < L`` (caller did not clamp), first ``h`` steps are 1
    and the remainder are 0.
    """
    h_i = int(h)
    L = int(length)
    if h_i < 0:
        raise ValueError(f"partition_height h must be >= 0; got {h_i}")
    if L < 1:
        raise ValueError(f"partition_height L must be >= 1; got {L}")
    if h_i == 0:
        return tuple(0 for _ in range(L))
    q, r = divmod(h_i, L)
    return tuple((q + 1) if i < r else q for i in range(L))


def length_from_target_angle(h: int, angle_deg: float) -> int:
    """Geom-B: ``L = ceil(h / tan θ)``, minimum 1."""
    h_i = max(0, int(h))
    if h_i < 1:
        return 1
    theta = float(angle_deg)
    if theta <= 0.0 or theta >= 90.0:
        raise ValueError(f"target_angle_deg must be in (0, 90); got {theta}")
    tan_t = math.tan(math.radians(theta))
    if tan_t <= 0.0:
        raise ValueError(f"tan(target_angle_deg) must be > 0; got θ={theta}")
    return max(1, math.ceil(h_i / tan_t))


def angle_from_height_length(h: int, length: int) -> float:
    """Geom-A derived θ in degrees (cubic cell: h=1,L=1 → 45)."""
    h_i = max(0, int(h))
    L = max(1, int(length))
    if h_i < 1:
        return 0.0
    return math.degrees(math.atan(h_i / L))


def geom_resolve(
    *,
    h: int,
    kind: ReliefSideKind,
    knobs: GeomKnobs | None = None,
    slope_length_cells: int | None = None,
    target_angle_deg: float | None = None,
) -> ResolvedGeom:
    """Resolve ``{h, L, angle_deg, steps}`` for SLOPE|SHEER (R36a–c, R36i).

    SLOPE: Geom-A (h+L→θ) or Geom-B (θ+h→L); then ``L_eff = min(L, h)``;
    ``steps = partition_height(h, L_eff)`` with ``sum(steps) == h``.

    SHEER: angle N/A; L from ``slope_length_cells`` (default 1) — Geom-B ignored;
    no height partition (volume fill is L columns × h solid — §8b).

    Explicit ``slope_length_cells=0`` → ``L=0``, empty ``steps`` (no wedge; no
    silent bump to 1). Omit L → default 1. ``partition_height`` only when L≥1.
    """
    h_i = abs(int(h))
    if knobs is not None:
        slope_length_cells = knobs.slope_length_cells
        target_angle_deg = knobs.target_angle_deg

    if kind is ReliefSideKind.SHEER:
        L = resolved_slope_length_cells(
            slope_length_cells,
            default=DEFAULT_SLOPE_LENGTH_CELLS,
        )
        if L < 1:
            return ResolvedGeom(
                kind=kind, h=h_i, L=0, angle_deg=None, steps=(),
            )
        return ResolvedGeom(
            kind=kind,
            h=h_i,
            L=L,
            angle_deg=None,
            steps=(),
        )

    if kind is not ReliefSideKind.SLOPE:
        raise ValueError(f"geom_resolve kind must be SLOPE|SHEER; got {kind!r}")

    if h_i < 1:
        return ResolvedGeom(
            kind=kind,
            h=0,
            L=0,
            angle_deg=0.0,
            steps=(),
        )

    if target_angle_deg is not None:
        L_raw = length_from_target_angle(h_i, float(target_angle_deg))
    else:
        L_raw = resolved_slope_length_cells(
            slope_length_cells,
            default=DEFAULT_SLOPE_LENGTH_CELLS,
        )
        if L_raw < 1:
            return ResolvedGeom(
                kind=kind, h=h_i, L=0, angle_deg=None, steps=(),
            )

    # Prefer no flat ramp tails (R36i): L_eff = min(L, h); L_raw >= 1 here
    L_eff = max(1, min(L_raw, h_i))
    steps = partition_height(h_i, L_eff)
    angle = angle_from_height_length(h_i, L_eff)
    return ResolvedGeom(
        kind=kind,
        h=h_i,
        L=L_eff,
        angle_deg=angle,
        steps=steps,
    )
