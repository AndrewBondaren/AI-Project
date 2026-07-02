"""
Проверки высоты прохода — пре- и пост-генерация.
"""
from __future__ import annotations

import logging

from app.dataModel.structure.enums.buildingElement import StructureElement
from app.application.worldData.generators.structure.structureElement import (
    _PASSABLE_ELEMENTS, _STAIR_ELEMENTS,
)

logger = logging.getLogger(__name__)


class PassageHeightChecker:
    def __init__(
        self,
        cells: dict,
        passage_height: int,
        min_height: int = 2,
    ) -> None:
        self.cells = cells
        self.passage_height = passage_height
        self.min_height = min_height

    @staticmethod
    def _blocks_headroom(elem: str) -> bool:
        return elem not in _PASSABLE_ELEMENTS

    def fits_column(self, x: int, y: int, z_start: int, h: int) -> bool:
        """Проверяет что в колонке (x,y) нет нестеновых элементов на h позиций от z_start."""
        for dz in range(h):
            cell = self.cells.get((x, y, z_start + dz))
            if cell is not None and cell.system_building_element != StructureElement.WALL:
                return False
        return True

    def resolve_height(
        self,
        positions: list[tuple[int, int]],
        z_start: int,
        desired: int,
    ) -> int | None:
        """
        Пробует desired → passage_height → min_height.
        Возвращает первую подходящую высоту или None если ничего не влезло.
        """
        seen: set[int] = set()
        for h in (desired, self.passage_height, self.min_height):
            if h in seen or h < self.min_height:
                continue
            seen.add(h)
            if all(self.fits_column(x, y, z_start, h) for x, y in positions):
                return h
        return None

    def check_headroom(
        self,
        path_cells: list[tuple[int, int, int]],
        conn_label: str,
        clearance: int,
        z_lo: int,
        z_top: int,
    ) -> None:
        """Пост-проверка: выбрасывает ValueError если headroom заблокирован."""
        for (x, y, z) in path_cells:
            for dz in range(1, clearance + 1):
                z_check = z + dz
                if z_check > z_top:
                    continue
                above = self.cells.get((x, y, z_check))
                if above is not None and self._blocks_headroom(above.system_building_element):
                    raise ValueError(
                        f"staircase {conn_label!r}: headroom blocked at "
                        f"({x},{y},z={z_check}) by {above.system_building_element!r}"
                    )

    def check_all_stair_headrooms(self, clearance: int = 2) -> None:
        """Пост-проверка всех stair-ячеек в self.cells."""
        for (x, y, z), cell in self.cells.items():
            if cell.system_building_element not in _STAIR_ELEMENTS:
                continue
            for dz in range(1, clearance + 1):
                above = self.cells.get((x, y, z + dz))
                if above is not None and self._blocks_headroom(above.system_building_element):
                    logger.error(
                        "headroom | (%d,%d,z=%d) %s blocked at z=%d by %s",
                        x, y, z, cell.system_building_element, z + dz,
                        above.system_building_element,
                    )
