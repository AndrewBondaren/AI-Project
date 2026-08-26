"""Leftover L=1 pair θ — tz_terrain_relief § Угол.

Not mill envelope plains 45° (``reliefTerrainEnvelope``). Pack occupancy
walk stays in ``pack/refine/gradeCellSlots``; this module is the pair rule.
"""

from __future__ import annotations

from app.dataModel.terrain.relief.gradeSlot import (
    GradeCouple,
    GradeOctant,
    GradeSeam,
    GradeSheer,
)
from app.dataModel.terrain.relief.reliefSlopeGeom import angle_from_height_length

# SoT generate § Угол: leftover pair step is one cell; SHEER is [80, 90).
LEFTOVER_PAIR_LENGTH_CELLS = 1
LEFTOVER_SHEER_MIN_DEG = 80.0


def leftover_pair_theta(abs_dz: int) -> float:
    return angle_from_height_length(int(abs_dz), LEFTOVER_PAIR_LENGTH_CELLS)


def leftover_pair_is_sheer(abs_dz: int) -> bool:
    return leftover_pair_theta(abs_dz) >= LEFTOVER_SHEER_MIN_DEG


def leftover_pair_code(abs_dz: int, flow: GradeOctant) -> int:
    if leftover_pair_is_sheer(abs_dz):
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
