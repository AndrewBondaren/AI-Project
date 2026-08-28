"""Locked-test leftover pack: downhill + COUPLE on leftover+halo.

Not persist. Sidecar writer is ``pack_cell_slots``. R44 invent-from-z stays
in ``gradeCellRays``. Do not import from mill/discover/FineChunkPersist.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping

from app.application.worldData.generators.terrain.relief.validate.gradeCellRays import (
    leftover_plus_halo,
)
from app.dataModel.terrain.relief.gradeRimRay import (
    GradeRimRay,
    couple_rim_rays,
    downhill_leftover_rim_rays,
    merge_grade_rim_rays,
    pack_rim_slot_rays,
)


def pack_slots_for_persist(
    senders: Iterable[GradeRimRay],
    z_height_map: Mapping[tuple[int, int], int],
    *,
    cells: Collection[tuple[int, int]] | None = None,
) -> tuple[tuple[GradeRimRay, ...], tuple[tuple[int, int], ...]]:
    """Leftover + downhill fill + COUPLE. Halo from mill leftover, not COUPLE."""
    allowed = set(cells) if cells is not None else {
        (int(x), int(y)) for x, y in z_height_map
    }
    leftover = pack_rim_slot_rays(senders, cells=allowed)
    halo = leftover_plus_halo(leftover, z_height_map)
    filled = merge_grade_rim_rays(
        leftover,
        downhill_leftover_rim_rays(leftover, z_height_map),
    )
    slots = merge_grade_rim_rays(
        filled,
        couple_rim_rays(halo, filled, z_height_map),
    )
    return slots, halo
