"""Occupancy 8-code row — SoT consume validator. Does not close from z.

R44 leftover+halo / invent-from-z lives in ``gradeCellRays`` (locked tests).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_CELL_EMPTY_RAY,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_error
from app.application.worldData.generators.terrain.relief.validate.emptySlotDiagram import (
    open_slot_diagram,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.terrain.relief.gradeSlot import (
    GRADE_SLOT_COUNT,
    GradeCellSlots,
    GradeOctant,
    facing_from_octant,
)


def validate_grade_cell_slots(
    occupancy: Iterable[tuple[int, int]],
    packed: Iterable[GradeCellSlots],
    *,
    z_height_map: Mapping[tuple[int, int], int],
    on_progress: Callable[[int, int], None] | None = None,
    progress_every: int = 0,
) -> int:
    """ERROR if an occupancy cell in the heightmap has no complete 8-code row.

    Does not invent SEAM/COUPLE from z. Generate continues. ``on_progress`` is
    the packBakeLog heartbeat, not a second ERROR logger.
    """
    by_cell = {cell.cell: cell for cell in packed}
    n_seen = 0
    n_empty = 0
    tick = max(0, int(progress_every))
    all_facings = {
        facing_from_octant(GradeOctant(position))
        for position in range(GRADE_SLOT_COUNT)
    }
    for xy in occupancy:
        key = (int(xy[0]), int(xy[1]))
        if key not in z_height_map:
            continue
        n_seen += 1
        cell = by_cell.get(key)
        missing_set = all_facings if cell is None else set()
        if missing_set:
            n_empty += 1
            missing = tuple(facing.value for facing in Facing if facing in missing_set)
            slots, open_ids = open_slot_diagram(missing_set)
            relief_error(
                EVENT_GRADE_CELL_EMPTY_RAY,
                x=key[0],
                y=key[1],
                empty_facings=missing,
                slots=slots,
                open=open_ids,
            )
        if on_progress is not None and tick and n_seen % tick == 0:
            on_progress(n_seen, n_empty)
    if on_progress is not None and n_seen and (tick == 0 or n_seen % tick != 0):
        on_progress(n_seen, n_empty)
    return n_empty
