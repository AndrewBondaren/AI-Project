"""
Пост-обработка структуры здания.

Вызывается после build_passages — когда все ячейки (staircase, wall, floor, void)
уже в финальном состоянии. Каждая функция мутирует cells_dict на месте.
"""
import logging
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)

_DIRS = [(1, 0, "E"), (-1, 0, "W"), (0, 1, "N"), (0, -1, "S")]


def _apply_railings(cells: dict[tuple, MapCell]) -> None:
    """
    Ставит railing_sides на floor-ячейки, у которых есть горизонтальный void-сосед
    на том же z. Поручень ставится на грань, смотрящую в пустоту.
    """
    count = 0
    for (x, y, z), cell in cells.items():
        if cell.system_building_element != "floor":
            continue
        sides = [
            face for dx, dy, face in _DIRS
            if cells.get((x + dx, y + dy, z)) is not None
            and cells[(x + dx, y + dy, z)].system_building_element == "void"
        ]
        if not sides:
            continue
        cell.railing_sides = sorted(sides)
        count += 1
        logger.info(
            "railing | z=%d | cell=(%d,%d) sides=%s",
            z, x, y, cell.railing_sides,
        )
    logger.info("post_process | railings placed: %d", count)


def run(cells: dict[tuple, MapCell]) -> None:
    """Все пост-обработки структуры в порядке применения."""
    _apply_railings(cells)
