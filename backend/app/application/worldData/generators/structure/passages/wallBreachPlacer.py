"""
Централизованное размещение пробоин в стенах.

place_for_shaft()    — пробой стены на полную высоту шахты:
                       1 door на z_lo + open выше (вертикальный проход).
place_for_corridor() — пробой стены для горизонтального тоннеля:
                       passage_height door-ячеек снизу + open выше.

Размещение двери делегируется в DoorPlacer — единственное место с проверкой floor.
"""
from __future__ import annotations

import logging

from app.application.worldData.generators.structure.cellFactory import _floor_cell, _open_cell
from app.application.worldData.generators.utils.facing import Facing
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer

logger = logging.getLogger(__name__)


class WallBreachPlacer:
    def __init__(self, cells: dict, world_uid: str, building_uid: str) -> None:
        self._cells = cells
        self._wu    = world_uid
        self._bu    = building_uid

    def place_for_archway(
        self,
        x: int,
        y: int,
        z_lo: int,
        z_hi: int,
        mat: str,
    ) -> None:
        """Floor на z_lo + open на z_lo+1..z_hi-1, без двери."""
        self._cells[(x, y, z_lo)] = _floor_cell(x, y, z_lo, self._wu, self._bu, mat)
        for z in range(z_lo + 1, z_hi):
            self._cells[(x, y, z)] = _open_cell(x, y, z, self._wu, self._bu, mat)

    def place_for_shaft(
        self,
        x: int,
        y: int,
        z_lo: int,
        z_top: int,
        mat: str,
        facing: Facing,
        conn_label: str = "?",
    ) -> bool:
        """Дверь на z_lo + open на z_lo+1..z_top-1."""
        placer = DoorPlacer(self._cells, self._wu, self._bu)
        placed = placer.place(x, y, z_lo, mat, height=1, facing=facing, conn_label=conn_label)
        if not placed:
            return False
        for z in range(z_lo + 1, z_top):
            self._cells[(x, y, z)] = _open_cell(x, y, z, self._wu, self._bu, mat)
        return True

    def place_for_corridor(
        self,
        x: int,
        y: int,
        z_lo: int,
        z_top: int,
        mat: str,
        facing: Facing,
        passage_height: int,
        conn_label: str = "?",
    ) -> bool:
        """passage_height door-ячеек от z_lo + open выше до z_top-1."""
        door_top = min(z_lo + passage_height, z_top)
        placer = DoorPlacer(self._cells, self._wu, self._bu)
        placed = placer.place(x, y, z_lo, mat, height=door_top - z_lo, facing=facing, conn_label=conn_label)
        if not placed:
            return False
        for z in range(door_top, z_top):
            self._cells[(x, y, z)] = _open_cell(x, y, z, self._wu, self._bu, mat)
        return True
