"""
Централизованное размещение дверей.

Используется всеми builder'ами, ставящими двери:
  - doorway.py (двери между комнатами)
  - entry.py   (входные двери)

Пробоины в стенах (wall breach) — см. wallBreachPlacer.py.
"""
from __future__ import annotations

import logging

from app.application.worldData.generators.utils.facing import Facing
from app.application.worldData.generators.structure.cellFactory import _door_cell
from app.application.worldData.generators.structure.passages.doorValidator import (
    _THROUGH,
    validate_door_cell,
)
from app.application.worldData.generators.structure.structureElement import StructureElement

logger = logging.getLogger(__name__)


class DoorPlacer:
    """Размещает двери в cells-словаре."""

    def __init__(self, cells: dict, world_uid: str, building_uid: str) -> None:
        self._cells = cells
        self._wu    = world_uid
        self._bu    = building_uid

    def filter_passable_from_center(
        self,
        candidates: list[tuple[int, int]],
        z: int,
        facing: Facing,
        allow_exterior: bool = False,
    ) -> list[tuple[int, int]]:
        """Возвращает только те кандидаты, у которых обе через-ячейки — floor.
        allow_exterior=True: None-ячейка (улица) тоже принимается (для entry-точек).
        """
        tdx, tdy = _THROUGH[facing]
        center_idx = len(candidates) // 2
        result = []
        for i, (x, y) in enumerate(candidates):
            ok = True
            for nx, ny in [(x + tdx, y + tdy), (x - tdx, y - tdy)]:
                nb   = self._cells.get((nx, ny, z))
                elem = nb.system_building_element if nb else None
                if elem is None:
                    if not allow_exterior:
                        ok = False
                        break
                elif elem != StructureElement.FLOOR:
                    ok = False
                    break
            if ok:
                result.append((abs(i - center_idx), x, y))
        result.sort(key=lambda t: t[0])
        return [(x, y) for _, x, y in result]

    def place(
        self,
        x: int,
        y: int,
        z: int,
        mat: str,
        height: int,
        facing: Facing,
        conn_label: str = "?",
        allow_exterior: bool = False,
    ) -> bool:
        """
        Проверяет наличие floor по обе стороны двери, затем ставит дверь.
        allow_exterior=True: None-ячейка (улица) принимается (для entry-точек).
        Возвращает False и не ставит дверь, если через-ячейка не floor.
        """
        tdx, tdy = _THROUGH[facing]
        for nx, ny in [(x + tdx, y + tdy), (x - tdx, y - tdy)]:
            nb   = self._cells.get((nx, ny, z))
            elem = nb.system_building_element if nb else None
            if elem is None:
                if not allow_exterior:
                    logger.error(
                        "door %s (%d,%d,z=%d) facing=%s: через (%d,%d)=None — внешнее пространство недопустимо",
                        conn_label, x, y, z, facing.value, nx, ny,
                    )
                    return False
            elif elem != StructureElement.FLOOR:
                logger.error(
                    "door %s (%d,%d,z=%d) facing=%s: через (%d,%d)=%s — нет floor, не ставим",
                    conn_label, x, y, z, facing.value, nx, ny, elem,
                )
                return False

        for dz in range(height):
            self._cells[(x, y, z + dz)] = _door_cell(
                x, y, z + dz, self._wu, self._bu, mat, facing=facing.value,
            )
        validate_door_cell(self._cells, x, y, z, facing, conn_label)
        return True
