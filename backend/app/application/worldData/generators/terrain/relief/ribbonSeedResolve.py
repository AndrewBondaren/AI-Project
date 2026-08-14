"""Per-seed clearance resolve (outward + free_gap → L_eff) — R36 §9 phase."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.application.worldData.generators.terrain.relief.freeGap import measure_free_gap
from app.application.worldData.generators.terrain.relief.gradeObstacleLight import (
    is_grade_obstacle_light,
)
from app.application.worldData.generators.terrain.relief.obstacleClearance import (
    outward_length,
)
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    WHY_CLEARANCE_L_EFF,
    WHY_NO_UNIQUE_OUTWARD,
)
from app.application.worldData.generators.terrain.relief.shoulderWidth import (
    unique_outward,
)

Coord = tuple[int, int]
CellBlockedFn = Callable[[Coord], bool]


@dataclass(frozen=True, slots=True)
class SeedClearance:
    """Successful clearance for one shoulder seed."""

    seed: Coord
    outward: tuple[int, int]
    free_gap: int
    L_eff: int


@dataclass(frozen=True, slots=True)
class SeedClearanceSkip:
    seed: Coord
    why: str
    free_gap: int | None = None
    requested: int | None = None
    L_eff: int | None = None


def resolve_seed_clearance(
    *,
    seed: Coord,
    ref_cells: set[Coord],
    requested_length: int,
    world: Any,
    cell_blocked: CellBlockedFn,
    flush_void: bool = False,
) -> SeedClearance | SeedClearanceSkip:
    """Phase 1: outward + gap + world policy → ``L_eff`` or skip.

    ``flush_void``: stop cell is past a catalog face with < 2 chunk parents
    (open rim of this tile). Not a C18 obstacle — use the free cells (R36w).
    Internal missing column (2 chunk parents) still uses world policy.
    """
    outward = unique_outward(seed, ref_cells)
    if outward is None:
        return SeedClearanceSkip(seed=seed, why=WHY_NO_UNIQUE_OUTWARD)

    def _blocked(cell: Coord) -> bool:
        return is_grade_obstacle_light(
            cell, ref_cells=ref_cells, cell_blocked=cell_blocked,
        )

    gap = measure_free_gap(start=seed, outward=outward, is_blocked=_blocked)
    requested = max(0, int(requested_length))
    if flush_void:
        L_eff = max(0, min(requested, gap))
    else:
        L_eff = outward_length(
            world=world,
            requested_length=requested,
            free_gap=gap,
        )
    if L_eff < 1:
        return SeedClearanceSkip(
            seed=seed,
            why=WHY_CLEARANCE_L_EFF,
            free_gap=gap,
            requested=requested,
            L_eff=L_eff,
        )
    return SeedClearance(
        seed=seed, outward=outward, free_gap=gap, L_eff=L_eff,
    )
