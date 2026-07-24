"""Ridge-quantized mountain placement — shared light/coarse (tz Q4)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.application.worldData.masks.mountainField import is_mountain_autoresolve
from app.dataModel.terrainMasks.worldTerrainMasks import MountainsCategoryPolicy


@dataclass(frozen=True, slots=True)
class RidgeCandidate:
    origin_x_m: int
    origin_y_m: int
    typical_elevation_z: int


def iter_ridge_cells_in_meter_rect(
    *,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    ridge_cell_m: int,
) -> Iterable[tuple[int, int, int, int]]:
    """Yield (qx, qy, origin_x_m, origin_y_m) for ridge cells overlapping AABB."""
    ridge_m = max(1, int(ridge_cell_m))
    qx0, qy0 = x0 // ridge_m, y0 // ridge_m
    qx1, qy1 = x1 // ridge_m, y1 // ridge_m
    for qy in range(qy0, qy1 + 1):
        for qx in range(qx0, qx1 + 1):
            ox = qx * ridge_m + ridge_m // 2
            oy = qy * ridge_m + ridge_m // 2
            yield qx, qy, ox, oy


def place_ridge_candidates(
    *,
    seed: int,
    policy: MountainsCategoryPolicy,
    cells: Iterable[tuple[int, int, int, int]],
    typical_of: Callable[[int, int], int],
    accept: Callable[[int, int], bool] | None = None,
) -> list[RidgeCandidate]:
    """Shared autoresolve placement: ridge cells → candidates (not paint).

    ``cells``: (qx, qy, origin_x_m, origin_y_m).
    ``typical_of(ox, oy)`` → elevation bias for score.
    ``accept(ox, oy)`` optional filter (e.g. light tile set).
    """
    if not policy.autoresolve:
        return []
    seen: set[tuple[int, int]] = set()
    out: list[RidgeCandidate] = []
    for qx, qy, ox, oy in cells:
        if (qx, qy) in seen:
            continue
        if accept is not None and not accept(ox, oy):
            continue
        typical = int(typical_of(ox, oy))
        if not is_mountain_autoresolve(
            seed=seed,
            xm=ox,
            ym=oy,
            surface_z=typical,
            typical_elevation_z=typical,
            policy=policy,
        ):
            continue
        seen.add((qx, qy))
        out.append(
            RidgeCandidate(
                origin_x_m=ox,
                origin_y_m=oy,
                typical_elevation_z=typical,
            )
        )
    return out
