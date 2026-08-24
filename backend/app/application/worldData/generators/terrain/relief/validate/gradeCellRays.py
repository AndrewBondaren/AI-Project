"""R44 / C43: empty Facing slot on a surface cell.

SoT: ``docs/tz_terrain_relief_consume.md``. Does not invent leftover rays or abort.
Equal-z neighbor = unified-surface coupling (fills the slot, not a pack ray).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_CELL_EMPTY_RAY,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_error
from app.dataModel.spatial.facing import COMPACT_LETTER, Facing, GRID_OUTWARD_DELTA
from app.dataModel.terrain.relief.gradeRimRay import GradeRimRay, unified_surface_facings

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
    z_at: Mapping[tuple[int, int], int],
    couples: frozenset[Facing],
) -> bool:
    if facing in present:
        return True
    if facing in couples:
        return True
    dx, dy = GRID_OUTWARD_DELTA[facing]
    nb = (cell[0] + dx, cell[1] + dy)
    if nb not in z_at:
        return True
    return False


def grade_ray_universe(
    rays: Iterable[GradeRimRay],
    z_at: Mapping[tuple[int, int], int],
) -> tuple[tuple[int, int], ...]:
    """R44 universe: ray cells plus 8-halo that exist in ``z_at``. Not all plains."""
    cells: set[tuple[int, int]] = set()
    for ray in rays:
        cx, cy = int(ray.x), int(ray.y)
        origin = (cx, cy)
        if origin in z_at:
            cells.add(origin)
        for dx, dy in GRID_OUTWARD_DELTA.values():
            nb = (cx + dx, cy + dy)
            if nb in z_at:
                cells.add(nb)
    return tuple(sorted(cells))


def validate_grade_cell_empty_rays(
    cells: Iterable[tuple[int, int]],
    rays: Iterable[GradeRimRay],
    *,
    z_at: Mapping[tuple[int, int], int],
    on_progress: Callable[[int, int], None] | None = None,
    progress_every: int = 0,
) -> int:
    """ERROR per cell with a different-z neighbor and no pack slot. Generate continues.

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
        couples = unified_surface_facings(key, z_at)
        missing_set = {
            facing
            for facing in Facing
            if not _slot_closed(
                key, facing, present=present, z_at=z_at, couples=couples,
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
