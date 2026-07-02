"""
Z-position strategies for wall openings.

ZAdjuster decides at which absolute Z level(s) openings are placed.
Works independently from WallDistributor (XY placement).

ZAdjuster.resolve(z_base, z_height) → list[int]
    z_base   — absolute Z of the room floor (level.z)
    z_height — room ceiling height in cells (room.z_height)
    Returns  — list of absolute Z values; WallDistributor runs for each.

WindowHeightResolver decides how many z-levels a window spans.
    calculate(z_height) → int
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from app.dataModel.structure.enums.buildingElement import StructureElement


class WindowHeightResolver(ABC):
    @abstractmethod
    def calculate(self, z_height: int) -> int:
        ...


class ProportionalWindowHeight(WindowHeightResolver):
    def __init__(self, ratio: float) -> None:
        self._ratio = ratio

    def calculate(self, z_height: int) -> int:
        return max(1, int(z_height * self._ratio))


class ZAdjuster(ABC):
    @abstractmethod
    def resolve(self, z_base: int, z_height: int) -> list[int]:
        ...


class MiddleCellZAdjuster(ZAdjuster):
    """
    Centered window spanning height_resolver.calculate(z_height) z-levels.
    Window is centered vertically: start = (z_height - window_h) // 2
    """

    def __init__(self, height_resolver: WindowHeightResolver) -> None:
        self._height = height_resolver

    def resolve(self, z_base: int, z_height: int) -> list[int]:
        if z_height <= 0:
            return []
        wh = self._height.calculate(z_height)
        start = z_base + (z_height - wh) // 2
        return list(range(start, start + wh))


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

_MIDDLE_CELL = MiddleCellZAdjuster(ProportionalWindowHeight(0.4))

ZADJUSTER_BY_TYPE: dict[StructureElement, ZAdjuster] = {
    StructureElement.WINDOW:     _MIDDLE_CELL,
    StructureElement.PORTHOLE:   _MIDDLE_CELL,
    StructureElement.VENT:       _MIDDLE_CELL,
    StructureElement.ARROW_SLIT: _MIDDLE_CELL,
}
