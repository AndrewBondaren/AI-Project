"""
Z-position strategies for wall openings.

ZAdjuster decides at which absolute Z level(s) openings are placed.
Works independently from WallDistributor (XY placement).

ZAdjuster.resolve(z_base, z_height) → list[int]
    z_base   — absolute Z of the room floor (level.z)
    z_height — room ceiling height in cells (room.z_height)
    Returns  — list of absolute Z values; WallDistributor runs for each.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from app.application.worldData.generators.structure.structureElement import StructureElement


class ZAdjuster(ABC):
    @abstractmethod
    def resolve(self, z_base: int, z_height: int) -> list[int]:
        ...


class MiddleCellZAdjuster(ZAdjuster):
    """
    Mid-height wall cell (floor=0, ceiling=z_height-1).
    Formula: z_height // 2
    z_height=3 → offset=1, z_height=4 → offset=2, z_height=5 → offset=2
    """

    def resolve(self, z_base: int, z_height: int) -> list[int]:
        if z_height <= 0:
            return []
        return [z_base + z_height // 2]


class ShaftZAdjuster(ZAdjuster):
    """
    Evenly distributed Z positions along shaft height.
    z_base = fr_anchor (z_lo), z_height = z_top - z_lo.
    Used for automatic windows on external shaft walls — separate phase from wall_openings.
    Count derived from shaft height: one window per floor_z_height units.
    """

    def __init__(self, floor_z_height: int = 3) -> None:
        self._floor_z = floor_z_height

    def resolve(self, z_base: int, z_height: int) -> list[int]:
        if z_height <= 0:
            return []
        count = max(1, z_height // self._floor_z)
        spacing = z_height / count
        return [z_base + math.floor(spacing * i + spacing / 2) for i in range(count)]


# ---------------------------------------------------------------------------
# Registry

_MIDDLE_CELL = MiddleCellZAdjuster()

ZADJUSTER_BY_TYPE: dict[StructureElement, ZAdjuster] = {
    StructureElement.WINDOW:     _MIDDLE_CELL,
    StructureElement.PORTHOLE:   _MIDDLE_CELL,
    StructureElement.VENT:       _MIDDLE_CELL,
    StructureElement.ARROW_SLIT: _MIDDLE_CELL,
}
