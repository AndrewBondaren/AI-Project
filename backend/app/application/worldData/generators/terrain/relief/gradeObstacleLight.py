"""v1 light-grid grade obstacle predicate — tz_terrain_relief R36m §9.

Obstacles: road footprint | caller ``blocked`` (pin / OOB / missing).
Barrier/structure masks — later (not in v1).
"""

from __future__ import annotations

from collections.abc import Callable

Coord = tuple[int, int]
CellBlockedFn = Callable[[Coord], bool]


def is_grade_obstacle_light(
    cell: Coord,
    *,
    road_cells: set[Coord],
    cell_blocked: CellBlockedFn,
) -> bool:
    """``True`` if grade must not enter ``cell``.

    ``cell_blocked``: bake adapter for OOB / missing / ``location_pin``.
    """
    if cell in road_cells:
        return True
    return bool(cell_blocked(cell))
