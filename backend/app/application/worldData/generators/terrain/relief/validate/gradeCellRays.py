"""R44 / C43: empty Facing slot on a surface cell.

SoT: ``docs/tz_terrain_relief_consume.md``. Does not invent leftover rays or abort.
Equal-z without a pack COUPLE slot is empty (ERROR). Does not close from z.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_CELL_EMPTY_RAY,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_error
from app.dataModel.spatial.facing import COMPACT_LETTER, Facing, GRID_OUTWARD_DELTA
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay, leftover_pack_kind
from app.dataModel.terrain.relief.gradeSlot import (
    GRADE_SLOT_COUNT,
    GradeCellSlots,
    GradeOctant,
    facing_from_octant,
)

# Same 3×3 as tz_terrain_relief_consume ASCII (center is the terrain cell, always closed).
_CELL_SLOTS: tuple[tuple[Facing | None, ...], ...] = (
    (Facing.NORTHWEST, Facing.NORTH, Facing.NORTHEAST),
    (Facing.WEST, None, Facing.EAST),
    (Facing.SOUTHWEST, Facing.SOUTH, Facing.SOUTHEAST),
)


def _open_slots(missing: set[Facing]) -> tuple[str, str]:
    """`.` = unclosed edge; ``#`` = closed edge or center. ``open`` = compact letters."""

    def glyph(slot: Facing | None) -> str:
        if slot is None:
            return "#"
        return "." if slot in missing else "#"

    diagram = " ".join("".join(glyph(slot) for slot in row) for row in _CELL_SLOTS)
    open_ids = ",".join(
        COMPACT_LETTER[slot]
        for row in _CELL_SLOTS
        for slot in row
        if slot is not None and slot in missing
    )
    return diagram, open_ids


def _slot_closed(
    cell: tuple[int, int],
    facing: Facing,
    *,
    present: set[Facing],
    z_height_map: Mapping[tuple[int, int], int],
) -> bool:
    if facing in present:
        return True
    dx, dy = GRID_OUTWARD_DELTA[facing]
    nb = (cell[0] + dx, cell[1] + dy)
    return nb not in z_height_map


def leftover_plus_halo(
    rays: Iterable[GradeRimRay],
    z_height_map: Mapping[tuple[int, int], int],
) -> tuple[tuple[int, int], ...]:
    """Leftover SLOPE/SHEER cells plus their 8-neighbors in ``z_height_map``.

    R44 walks this set. Ignores COUPLE. Not all plains of the tile.
    """
    cells: set[tuple[int, int]] = set()
    for ray in rays:
        if not leftover_pack_kind(ray.kind):
            continue
        cx, cy = int(ray.x), int(ray.y)
        origin = (cx, cy)
        if origin in z_height_map:
            cells.add(origin)
        for dx, dy in GRID_OUTWARD_DELTA.values():
            nb = (cx + dx, cy + dy)
            if nb in z_height_map:
                cells.add(nb)
    return tuple(sorted(cells))


def validate_grade_cell_empty_rays(
    cells: Iterable[tuple[int, int]],
    rays: Iterable[GradeRimRay],
    *,
    z_height_map: Mapping[tuple[int, int], int],
    on_progress: Callable[[int, int], None] | None = None,
    progress_every: int = 0,
) -> int:
    """ERROR per cell with a neighbor in the heightmap and no pack slot.

    Same-z without COUPLE in pack is empty. Generate continues.
    Returns the number of cells that logged ERROR. ``on_progress(seen, empty)``
    is for packBakeLog heartbeats — not a second logger for the ERROR itself.
    """
    by_cell: dict[tuple[int, int], set[Facing]] = {}
    for ray in rays:
        by_cell.setdefault(ray.cell, set()).add(ray.facing)
    n_seen = 0
    n_empty = 0
    tick = max(0, int(progress_every))
    for x, y in cells:
        key = (int(x), int(y))
        n_seen += 1
        present = by_cell.get(key, set())
        missing_set = {
            facing
            for facing in Facing
            if not _slot_closed(
                key, facing, present=present, z_height_map=z_height_map,
            )
        }
        if missing_set:
            n_empty += 1
            missing = tuple(facing.value for facing in Facing if facing in missing_set)
            slots, open_ids = _open_slots(missing_set)
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
            slots, open_ids = _open_slots(missing_set)
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
