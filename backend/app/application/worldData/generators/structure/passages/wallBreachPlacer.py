"""
Централизованное размещение пробоин в стенах.

place_for_shaft()    — пробой стены на полную высоту шахты:
                       1 door на z_lo + open выше (вертикальный проход).
place_for_corridor() — пробой стены для горизонтального тоннеля:
                       passage_height door-ячеек снизу + open выше.
"""
from __future__ import annotations

from app.application.worldData.generators.structure.cellFactory import _door_cell, _open_cell
from app.application.worldData.generators.facing import Facing
from app.application.worldData.generators.structure.passages.doorValidator import validate_door_cell


class WallBreachPlacer:
    def __init__(self, cells: dict, world_uid: str, building_uid: str) -> None:
        self._cells = cells
        self._wu    = world_uid
        self._bu    = building_uid

    def place_for_shaft(
        self,
        x: int,
        y: int,
        z_lo: int,
        z_top: int,
        mat: str,
        facing: Facing,
        conn_label: str = "?",
    ) -> None:
        """
        Дверь на z_lo + open на z_lo+1..z_top-1.
        Используется когда шахта пробивает стену и виден вертикальный проём.
        """
        self._cells[(x, y, z_lo)] = _door_cell(
            x, y, z_lo, self._wu, self._bu, mat, facing=facing.value,
        )
        for z in range(z_lo + 1, z_top):
            self._cells[(x, y, z)] = _open_cell(x, y, z, self._wu, self._bu, mat)
        validate_door_cell(self._cells, x, y, z_lo, facing, conn_label)

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
    ) -> None:
        """
        passage_height door-ячеек от z_lo + open выше до z_top-1.
        Используется когда горизонтальный тоннель пробивает стену нижней комнаты.
        """
        door_top = min(z_lo + passage_height, z_top)
        for z in range(z_lo, door_top):
            self._cells[(x, y, z)] = _door_cell(
                x, y, z, self._wu, self._bu, mat, facing=facing.value,
            )
        for z in range(door_top, z_top):
            self._cells[(x, y, z)] = _open_cell(x, y, z, self._wu, self._bu, mat)
        validate_door_cell(self._cells, x, y, z_lo, facing, conn_label)
