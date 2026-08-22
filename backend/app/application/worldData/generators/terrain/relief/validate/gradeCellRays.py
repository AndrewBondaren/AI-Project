"""R44 / C43: empty Facing slot on a surface cell.

SoT: ``docs/tz_terrain_relief_consume.md``. Does not invent rays or abort generate.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_CELL_EMPTY_RAY,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_error
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay


def validate_grade_cell_empty_rays(
    cells: Iterable[tuple[int, int]],
    rays: Iterable[GradeRimRay],
) -> None:
    """ERROR per cell with any empty pack slot. Generate continues."""
    by_cell: dict[tuple[int, int], set[Facing]] = {}
    for ray in rays:
        by_cell.setdefault(ray.cell, set()).add(ray.facing)
    for x, y in cells:
        key = (int(x), int(y))
        present = by_cell.get(key, set())
        missing = tuple(facing.value for facing in Facing if facing not in present)
        if not missing:
            continue
        relief_error(
            EVENT_GRADE_CELL_EMPTY_RAY,
            x=key[0],
            y=key[1],
            empty_facings=missing,
        )
