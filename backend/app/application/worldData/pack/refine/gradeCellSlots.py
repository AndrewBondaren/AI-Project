"""Pack occupancy slots from ``z_height_map`` pairs — tz_terrain_relief § Правила стрелок.

Not mill leftover, not ``slope_outcome`` 45°. Glyphs are dump-only.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from app.dataModel.terrain.relief.gradeSlot import (
    GRADE_SLOT_COUNT,
    GradeCellSlots,
    GradeCouple,
    GradeOctant,
    GradeSeam,
    GradeSheer,
    neighbor_cell,
)
from app.dataModel.terrain.relief.reliefSlopeGeom import angle_from_height_length

# Leftover L=1 vs mill envelope 45°. SoT generate § Угол: SHEER [80, 90).
_LEFTOVER_SHEER_MIN_DEG = 80.0


def leftover_pair_code(abs_dz: int, flow: GradeOctant) -> int:
    theta = angle_from_height_length(int(abs_dz), 1)
    if theta >= _LEFTOVER_SHEER_MIN_DEG:
        return int(GradeSheer.SHEER)
    return int(flow)


def slot_code_for_neighbor(z_cell: int, z_neighbor: int | None, position: int) -> int:
    if z_neighbor is None:
        return int(GradeSeam.SEAM)
    zc = int(z_cell)
    zn = int(z_neighbor)
    if zn == zc:
        return int(GradeCouple.COUPLE)
    flow = GradeOctant(int(position))
    if zc < zn:
        flow = flow.opposite()
    return leftover_pair_code(abs(zc - zn), flow)


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
