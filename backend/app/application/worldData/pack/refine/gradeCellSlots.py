"""Walk occupancy → 8 codes. Pair rules: ``dataModel.terrain.relief.gradeLeftoverPair``.

Not mill leftover, not ``slope_outcome`` 45°. Glyphs are dump-only.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from app.dataModel.terrain.relief.gradeLeftoverPair import slot_code_for_neighbor
from app.dataModel.terrain.relief.gradeSlot import GRADE_SLOT_COUNT, GradeCellSlots, neighbor_cell


def pack_cell_slots(
    z_height_map: Mapping[tuple[int, int], int],
    *,
    cells: Collection[tuple[int, int]] | None = None,
) -> tuple[GradeCellSlots, ...]:
    """One ``GradeCellSlots`` per occupancy cell. Neighbor lookup is ``z_height_map``.

    Default occupancy = every key in the heightmap (unit bake). Missing neighbor
    key → ``SEAM``. Same z → ``COUPLE``. Other z → one flow (Octant or SHEER).
    """
    occupancy = cells if cells is not None else z_height_map.keys()
    out: list[GradeCellSlots] = []
    for xy in sorted((int(x), int(y)) for x, y in occupancy):
        z_cell = z_height_map.get(xy)
        if z_cell is None:
            continue
        zc = int(z_cell)
        slots = []
        for position in range(GRADE_SLOT_COUNT):
            nb = neighbor_cell(xy, position)
            raw = z_height_map.get(nb)
            zn = None if raw is None else int(raw)
            slots.append(slot_code_for_neighbor(zc, zn, position))
        out.append(GradeCellSlots(x=xy[0], y=xy[1], slots=tuple(slots)))
    return tuple(out)
