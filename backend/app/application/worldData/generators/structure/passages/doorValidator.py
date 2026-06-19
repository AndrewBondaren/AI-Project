"""
Валидация размещения двери.

Дверь корректна если:
  - стороны «через» (вдоль facing): floor / door / archway / staircase / stair_anchor
  - стороны «рама» (перпендикулярно facing): wall

Используется из любого builder'а, ставящего дверь.
"""
from __future__ import annotations

import logging

from app.application.worldData.generators.structure.facing import Facing

logger = logging.getLogger(__name__)

_PASSABLE = {
    "floor", "door", "archway",
    "staircase", "stair_floor", "stair_anchor",
    "ladder", "trapdoor",
}

# ось «через» дверь (facing и противоположное) — (dx, dy)
_THROUGH: dict[Facing, tuple[int, int]] = {
    Facing.NORTH: (0, 1),
    Facing.SOUTH: (0, 1),
    Facing.EAST:  (1, 0),
    Facing.WEST:  (1, 0),
}
# ось «рама» (перпендикуляр)
_FRAME: dict[Facing, tuple[int, int]] = {
    Facing.NORTH: (1, 0),
    Facing.SOUTH: (1, 0),
    Facing.EAST:  (0, 1),
    Facing.WEST:  (0, 1),
}


def validate_door_cell(
    cells: dict,
    x: int,
    y: int,
    z: int,
    facing: Facing,
    conn_label: str = "?",
) -> None:
    """
    Проверяет корректность размещения двери на (x, y, z) с facing=facing.
    Логирует warning при нарушении — не бросает исключение.
    """
    tdx, tdy = _THROUGH[facing]
    fdx, fdy = _FRAME[facing]

    for (nx, ny), side in [
        ((x + tdx, y + tdy), "through+"),
        ((x - tdx, y - tdy), "through−"),
    ]:
        nb = cells.get((nx, ny, z))
        elem = nb.system_building_element if nb else None
        if elem not in _PASSABLE:
            logger.warning(
                "door %s (%d,%d,z=%d) facing=%s: %s=%s ожидается проходимая ячейка",
                conn_label, x, y, z, facing.value, side, elem,
            )

    for (nx, ny), side in [
        ((x + fdx, y + fdy), "frame+"),
        ((x - fdx, y - fdy), "frame−"),
    ]:
        nb = cells.get((nx, ny, z))
        elem = nb.system_building_element if nb else None
        if elem != "wall":
            logger.warning(
                "door %s (%d,%d,z=%d) facing=%s: %s=%s ожидается wall",
                conn_label, x, y, z, facing.value, side, elem,
            )
