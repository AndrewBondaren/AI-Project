"""
Валидация размещения арки.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PASSABLE = {
    "floor", "door", "archway",
    "staircase", "stair_floor", "stair_anchor",
    "ladder", "trapdoor",
}


def _line_axes(arch_cells: list[tuple[int, int]]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Возвращает (line_vec, through_vec) по первой и последней ячейке арки."""
    x0 = arch_cells[0][0]
    xn = arch_cells[-1][0]
    if x0 == xn:
        return (0, 1), (1, 0)   # вертикальная линия, проход по x
    return (1, 0), (0, 1)       # горизонтальная линия, проход по y


def validate_archway_frame(
    cells: dict,
    arch_cells: list[tuple[int, int]],
    z: int,
    conn_label: str = "?",
) -> None:
    """Концы линии арки с обеих сторон должны быть wall."""
    if not arch_cells:
        return
    (ldx, ldy), _ = _line_axes(arch_cells)
    x0, y0 = arch_cells[0]
    xn, yn = arch_cells[-1]
    for (nx, ny), side in [
        ((x0 - ldx, y0 - ldy), "frame_start"),
        ((xn + ldx, yn + ldy), "frame_end"),
    ]:
        nb = cells.get((nx, ny, z))
        elem = nb.system_building_element if nb else None
        if elem != "wall":
            logger.warning(
                "archway %s (z=%d): %s=(%d,%d) elem=%s — ожидается wall",
                conn_label, z, side, nx, ny, elem,
            )


def validate_all_archway_frames(cells: dict) -> None:
    """
    Постгенерационный скан: находит все горизонтальные и вертикальные прогоны
    archway-ячеек и проверяет что оба конца каждого прогона упираются в wall.
    """
    by_z: dict[int, set[tuple[int, int]]] = {}
    for (x, y, z), cell in cells.items():
        if cell.system_building_element == "archway":
            by_z.setdefault(z, set()).add((x, y))

    for z, pos_set in by_z.items():
        # Горизонтальные прогоны (одинаковый y, последовательный x)
        visited_h: set[tuple[int, int]] = set()
        for x, y in sorted(pos_set):
            if (x, y) in visited_h or (x - 1, y) in pos_set:
                continue
            run: list[tuple[int, int]] = []
            cx = x
            while (cx, y) in pos_set:
                run.append((cx, y))
                visited_h.add((cx, y))
                cx += 1
            _check_frame_h(cells, run, z)

        # Вертикальные прогоны (одинаковый x, последовательный y)
        visited_v: set[tuple[int, int]] = set()
        for x, y in sorted(pos_set, key=lambda p: (p[0], p[1])):
            if (x, y) in visited_v or (x, y - 1) in pos_set:
                continue
            run = []
            cy = y
            while (x, cy) in pos_set:
                run.append((x, cy))
                visited_v.add((x, cy))
                cy += 1
            _check_frame_v(cells, run, z)


def _check_frame_h(cells: dict, run: list[tuple[int, int]], z: int) -> None:
    """Проверка frame горизонтального прогона: стены слева и справа."""
    x0, y = run[0]
    xn, _ = run[-1]
    w_nb = cells.get((x0 - 1, y, z))
    e_nb = cells.get((xn + 1, y, z))
    w_elem = w_nb.system_building_element if w_nb else None
    e_elem = e_nb.system_building_element if e_nb else None
    if w_elem != "wall" and e_elem != "wall":
        return  # оба конца без стены — open-ячейки над аркой, не валидируем
    if w_elem != "wall":
        logger.error(
            "archway scan H (z=%d): y=%d x=%d..%d | frame_w=(%d,%d) elem=%s — ожидается wall",
            z, y, x0, xn, x0 - 1, y, w_elem,
        )
    if e_elem != "wall":
        logger.error(
            "archway scan H (z=%d): y=%d x=%d..%d | frame_e=(%d,%d) elem=%s — ожидается wall",
            z, y, x0, xn, xn + 1, y, e_elem,
        )


def _check_frame_v(cells: dict, run: list[tuple[int, int]], z: int) -> None:
    """Проверка frame вертикального прогона: стены сверху и снизу."""
    x, y0 = run[0]
    _, yn = run[-1]
    s_nb = cells.get((x, y0 - 1, z))
    n_nb = cells.get((x, yn + 1, z))
    s_elem = s_nb.system_building_element if s_nb else None
    n_elem = n_nb.system_building_element if n_nb else None
    if s_elem != "wall" and n_elem != "wall":
        return  # оба конца без стены — open-ячейки над аркой, не валидируем
    if s_elem != "wall":
        logger.error(
            "archway scan V (z=%d): x=%d y=%d..%d | frame_s=(%d,%d) elem=%s — ожидается wall",
            z, x, y0, yn, x, y0 - 1, s_elem,
        )
    if n_elem != "wall":
        logger.error(
            "archway scan V (z=%d): x=%d y=%d..%d | frame_n=(%d,%d) elem=%s — ожидается wall",
            z, x, y0, yn, x, yn + 1, n_elem,
        )


def validate_archway_through(
    cells: dict,
    arch_cells: list[tuple[int, int]],
    z: int,
    conn_label: str = "?",
) -> None:
    """По обе стороны прохода (перпендикулярно линии) каждая ячейка арки должна быть passable."""
    if not arch_cells:
        return
    _, (tdx, tdy) = _line_axes(arch_cells)
    for x, y in arch_cells:
        for nx, ny in [(x + tdx, y + tdy), (x - tdx, y - tdy)]:
            nb = cells.get((nx, ny, z))
            elem = nb.system_building_element if nb else None
            if elem not in _PASSABLE:
                logger.warning(
                    "archway %s (%d,%d,z=%d): through=(%d,%d) elem=%s — ожидается passable",
                    conn_label, x, y, z, nx, ny, elem,
                )
