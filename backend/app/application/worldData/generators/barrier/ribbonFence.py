"""Ortho fence footprint along ribbon grade cells — RELIEF-BAR-1 / R28.

Pure coords: no compose, no HTTP. Bake stamps ``wall``; clearance = caller.
"""

from __future__ import annotations

from collections.abc import Callable, Set

from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA

Coord = tuple[int, int]
AllowFn = Callable[[Coord], bool]

_ORTHO: tuple[tuple[int, int], ...] = tuple(CARDINAL_WALL_OUTWARD_DELTA.values())


def fence_cells_along_ribbon(
    grade_cells: Set[Coord],
    *,
    allow: AllowFn,
) -> set[Coord]:
    """Neighbors of grade cells (cardinal) that ``allow`` accepts.

    Typical ``allow``: not road, not grade, not pin/OOB/hydro/existing wall.
    """
    if not grade_cells:
        return set()
    out: set[Coord] = set()
    for gx, gy in grade_cells:
        for dx, dy in _ORTHO:
            n = (gx + dx, gy + dy)
            if n in grade_cells:
                continue
            if not allow(n):
                continue
            out.add(n)
    return out
