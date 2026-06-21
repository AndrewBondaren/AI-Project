"""
Централизованное размещение дверей.

Используется всеми builder'ами, ставящими двери:
  - doorway.py (двери между комнатами)
  - entry.py   (входные двери)

Пробоины в стенах (wall breach) — см. wallBreachPlacer.py.
"""
from __future__ import annotations

from app.application.worldData.generators.structure.cellFactory import _door_cell
from app.application.worldData.generators.facing import Facing
from app.application.worldData.generators.structure.passages.doorValidator import validate_door_cell


class DoorPlacer:
    """Размещает двери в cells-словаре."""

    def __init__(self, cells: dict, world_uid: str, building_uid: str) -> None:
        self._cells = cells
        self._wu    = world_uid
        self._bu    = building_uid

    def place(
        self,
        x: int,
        y: int,
        z: int,
        mat: str,
        height: int,
        facing: Facing | None = None,
        conn_label: str = "?",
    ) -> None:
        """Дверь на z высотой height ячеек. Валидирует, если передан facing."""
        for dz in range(height):
            self._cells[(x, y, z + dz)] = _door_cell(
                x, y, z + dz, self._wu, self._bu, mat,
                facing=facing.value if facing else None,
            )
        if facing:
            validate_door_cell(self._cells, x, y, z, facing, conn_label)
