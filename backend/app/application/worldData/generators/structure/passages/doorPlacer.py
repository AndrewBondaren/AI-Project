"""
Централизованное размещение дверей.

Используется всеми builder'ами, ставящими двери:
  - doorway.py          (двери между комнатами)
  - entry.py            (входные двери)
  - undergroundTunnel.py (пробив стены тоннелем)
"""
from __future__ import annotations

from app.application.worldData.generators.structure.cellFactory import _door_cell, _open_cell
from app.application.worldData.generators.structure.facing import Facing
from app.application.worldData.generators.structure.passages.doorValidator import validate_door_cell


class DoorPlacer:
    """
    Размещает двери в cells-словаре.

    place()             — одиночная дверь на одном z-уровне.
    place_wall_breach() — дверь на z_lo + open-ячейки выше (пробив многоуровневой стены).
    """

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
        facing: Facing | None = None,
        conn_label: str = "?",
    ) -> None:
        """Одиночная дверь на z. Валидирует, если передан facing."""
        self._cells[(x, y, z)] = _door_cell(
            x, y, z, self._wu, self._bu, mat,
            facing=facing.value if facing else None,
        )
        if facing:
            validate_door_cell(self._cells, x, y, z, facing, conn_label)

    def place_wall_breach(
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
        Дверь на z_lo + open-ячейки на z_lo+1..z_top-1.
        Применяется при пробиве стены, которая занимает несколько z-уровней.
        """
        self._cells[(x, y, z_lo)] = _door_cell(
            x, y, z_lo, self._wu, self._bu, mat, facing=facing.value,
        )
        for z in range(z_lo + 1, z_top):
            self._cells[(x, y, z)] = _open_cell(x, y, z, self._wu, self._bu, mat)
        validate_door_cell(self._cells, x, y, z_lo, facing, conn_label)
