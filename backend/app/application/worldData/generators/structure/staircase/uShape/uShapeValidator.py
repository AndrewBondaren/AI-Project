"""
U-shape staircase validator.
"""
import logging

from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.enums.buildingElement import (
    StructureElement, _STAIR_ELEMENTS, _STAIR_DIRECTIONAL,
)
from app.application.worldData.generators.structure.staircase.facingHelper import (
    _V_INIT, _V_TO_FACING,
)
from app.application.worldData.generators.structure.staircase.validator import StaircaseValidator

_NS = frozenset({Facing.NORTH, Facing.SOUTH})

logger = logging.getLogger(__name__)


# def _march_boundary_connected(
#     cells: dict,
#     sx: int, sy: int,
#     nx: int, ny: int,
#     z_t: int,
# ) -> bool:
#     """BFS через stair_floor ячейки на z_t от (sx,sy) до (nx,ny)."""
#     target = (nx, ny)
#     visited = {(sx, sy)}
#     queue = [(sx, sy)]
#     while queue:
#         cx, cy = queue.pop(0)
#         for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
#             ncx, ncy = cx + ddx, cy + ddy
#             if (ncx, ncy) in visited:
#                 continue
#             if (ncx, ncy) == target:
#                 return True
#             cell = cells.get((ncx, ncy, z_t))
#             if cell and cell.system_building_element == "stair_floor":
#                 visited.add((ncx, ncy))
#                 queue.append((ncx, ncy))
#     return False


def _traverse_stair_floor_chain(
    cells: dict,
    start: tuple[int, int, int],
    expected_next: tuple[int, int, int],
    conn_label: str,
    march_idx: int,
) -> int:
    """
    Traversal linked-list цепочки stair_floor начиная с start.
    Каждая stair_floor ячейка смотрит на следующую по system_facing (горизонтально, тот же z).
    Цепочка должна завершиться на expected_next (первая ступень следующего марша).
    Возвращает длину цепочки (кол-во пройденных stair_floor ячеек).
    """
    cx, cy, z = start
    visited: set[tuple[int, int, int]] = set()
    chain_len = 0
    while True:
        key = (cx, cy, z)
        if key in visited:
            logger.error(
                "u_shape %s [landing %d]: цикл в stair_floor цепочке на (%d,%d,z=%d)",
                conn_label, march_idx, cx, cy, z,
            )
            return chain_len
        visited.add(key)
        cell = cells.get(key)
        if cell is None:
            logger.error(
                "u_shape %s [landing %d]: нет ячейки на (%d,%d,z=%d)",
                conn_label, march_idx, cx, cy, z,
            )
            return chain_len
        elem = cell.system_building_element
        if elem in _STAIR_DIRECTIONAL:
            if key != expected_next:
                logger.error(
                    "u_shape %s [landing %d]: цепочка stair_floor привела к (%d,%d,z=%d), "
                    "ожидался (%d,%d,z=%d)",
                    conn_label, march_idx, cx, cy, z,
                    expected_next[0], expected_next[1], expected_next[2],
                )
            return chain_len
        if elem != StructureElement.STAIR_FLOOR:
            logger.error(
                "u_shape %s [landing %d]: неожиданный элемент %r на (%d,%d,z=%d)",
                conn_label, march_idx, elem, cx, cy, z,
            )
            return chain_len
        if not cell.system_facing:
            logger.error(
                "u_shape %s [landing %d]: stair_floor (%d,%d,z=%d) без facing",
                conn_label, march_idx, cx, cy, z,
            )
            return chain_len
        dx, dy = _V_INIT[cell.system_facing]
        cx, cy = cx + dx, cy + dy
        chain_len += 1


def _validate_stair_floor_chain(
    cells: dict,
    start: tuple[int, int, int],
    expected_next: tuple[int, int, int],
    conn_label: str,
    march_idx: int,
) -> None:
    """Стандартная валидация stair_floor цепочки (priority=CENTER)."""
    logger.info(
        "u_shape %s [landing %d]: priority=CENTER stair_floor от %s к %s",
        conn_label, march_idx, start, expected_next,
    )
    _traverse_stair_floor_chain(cells, start, expected_next, conn_label, march_idx)


def _validate_stair_floor_chain_corners(
    cells: dict,
    start: tuple[int, int, int],
    expected_next: tuple[int, int, int],
    conn_label: str,
    march_idx: int,
) -> None:
    """
    Валидация stair_floor цепочки для flat=2 corners (priority=CORNERS).
    Ожидает ровно 1 stair_floor ячейку — угловой переход между двумя staircase.
    """
    logger.info(
        "u_shape %s [landing %d]: priority=CORNERS stair_floor от %s к %s",
        conn_label, march_idx, start, expected_next,
    )
    chain_len = _traverse_stair_floor_chain(cells, start, expected_next, conn_label, march_idx)
    if chain_len != 1:
        logger.error(
            "u_shape %s [landing %d]: priority=CORNERS ожидает цепочку длиной 1, получено %d",
            conn_label, march_idx, chain_len,
        )


class UShapeValidator(StaircaseValidator):
    """
    Валидация якорей u_shape лестницы:

      fr_anchor:
        - stair_anchor на z_lo
        - внутри interior шахты
        - на ближней стороне шахты (near-side): первый марш идёт в сторону facing

      to_anchor:
        - floor вне interior шахты (стена шахты допустима — arch threshold)
        - сосед со стороны противоположной facing на z_top-1 — staircase-ячейка
    """

    def _check_stair_path(
        self,
        stair_cells: list[tuple[int, int, int]],
        cells: dict,
        conn_label: str,
    ) -> None:
        for idx, (sx, sy, sz) in enumerate(stair_cells[:-1]):
            s_cell = cells.get((sx, sy, sz))
            if not s_cell or not s_cell.system_facing:
                logger.error(
                    "u_shape %s [путь %d]: (%d,%d,z=%d) не имеет system_facing",
                    conn_label, idx, sx, sy, sz,
                )
                continue
            dx, dy = _V_INIT.get(s_cell.system_facing, (0, 0))
            if dx == 0 and dy == 0:
                logger.error(
                    "u_shape %s [путь %d]: (%d,%d,z=%d) неизвестный facing=%r",
                    conn_label, idx, sx, sy, sz, s_cell.system_facing,
                )
                continue
            nb = cells.get((sx + dx, sy + dy, sz + 1))
            nb_elem = nb.system_building_element if nb else "пусто"
            if nb_elem not in _STAIR_ELEMENTS:
                logger.error(
                    "u_shape %s [путь %d]: (%d,%d,z=%d) facing=%r -> (%d,%d,z=%d) = %r, "
                    "ожидался stair-элемент",
                    conn_label, idx, sx, sy, sz, s_cell.system_facing,
                    sx + dx, sy + dy, sz + 1, nb_elem,
                )
            elif nb_elem == StructureElement.STAIR_FLOOR:
                expected = stair_cells[idx + 1]
                chain_start = (sx + dx, sy + dy, sz + 1)
                # Dispatch: 1-клеточная цепочка → corners, длиннее → center.
                # Проверяем длину заранее через peek одного шага.
                peek_cell = cells.get(chain_start)
                peek_next = None
                if peek_cell and peek_cell.system_facing:
                    pdx, pdy = _V_INIT[peek_cell.system_facing]
                    peek_next = cells.get((chain_start[0] + pdx, chain_start[1] + pdy, chain_start[2]))
                is_corners = peek_next is not None and peek_next.system_building_element in _STAIR_DIRECTIONAL
                if is_corners:
                    _validate_stair_floor_chain_corners(
                        cells, start=chain_start, expected_next=expected,
                        conn_label=conn_label, march_idx=idx,
                    )
                else:
                    _validate_stair_floor_chain(
                        cells, start=chain_start, expected_next=expected,
                        conn_label=conn_label, march_idx=idx,
                    )

    def _check_anchors(
        self,
        fr_anchor:  tuple[int, int],
        to_anchor:  tuple[int, int],
        z_lo:       int,
        z_top:      int,
        cells:      dict,
        conn_label: str,
        **kwargs,
    ) -> None:
        fx, fy = fr_anchor
        tx, ty = to_anchor
        facing          = kwargs["facing"]
        exit_v          = kwargs["exit_v"]
        last_stair      = kwargs["last_stair"]
        shaft_interior  = kwargs["shaft_interior"]
        shaft_footprint = kwargs["shaft_footprint"]
        Vx, Vy = _V_INIT[facing]

        # ── fr_anchor: stair_anchor на z_lo ──────────────────────────────────
        fr_cell = cells.get((fx, fy, z_lo))
        got = fr_cell.system_building_element if fr_cell else "пусто"
        if got != StructureElement.STAIR_ANCHOR:
            logger.error(
                "u_shape %s [fr_anchor тип]: ячейка (%d,%d,z=%d) должна быть 'stair_anchor', "
                "получено %r. fr_anchor=%s, z_lo=%d, facing=%r",
                conn_label, fx, fy, z_lo, got, fr_anchor, z_lo, facing,
            )

        # ── fr_anchor: внутри interior шахты ─────────────────────────────────
        if (fx, fy) not in shaft_interior:
            xs = sorted({x for x, _ in shaft_interior})
            ys = sorted({y for _, y in shaft_interior})
            logger.error(
                "u_shape %s [fr_anchor interior]: якорь входа (%d,%d) вне interior шахты. "
                "interior x=%d..%d, y=%d..%d",
                conn_label, fx, fy, xs[0], xs[-1], ys[0], ys[-1],
            )

        # ── fr_anchor: near-side (первый марш идёт в сторону facing) ─────────
        if Vy > 0:
            near = min(y for _, y in shaft_interior)
            coord, val, axis = fy, near, "y"
        elif Vy < 0:
            near = max(y for _, y in shaft_interior)
            coord, val, axis = fy, near, "y"
        elif Vx > 0:
            near = min(x for x, _ in shaft_interior)
            coord, val, axis = fx, near, "x"
        else:
            near = max(x for x, _ in shaft_interior)
            coord, val, axis = fx, near, "x"

        if coord != val:
            logger.error(
                "u_shape %s [fr_anchor near-side]: якорь входа (%d,%d) должен быть "
                "на ближней стороне шахты (%s=%d) для facing=%r, получено %s=%d.",
                conn_label, fx, fy, axis, val, facing, axis, coord,
            )

        # ── to_anchor: floor вне interior шахты + лестница без якоря выхода ──
        self._check_to_anchor(cells, to_anchor, z_top, shaft_interior, shaft_footprint, conn_label)

        # ── to_anchor: сосед противоположной facing на z_top-1 — staircase ───
        Vx, Vy = exit_v
        nb_x, nb_y = tx - Vx, ty - Vy
        nb_cell = cells.get((nb_x, nb_y, z_top - 1))
        nb_elem = nb_cell.system_building_element if nb_cell else "пусто"
        if nb_elem not in _STAIR_ELEMENTS:
            logger.error(
                "u_shape %s [to_anchor сосед]: ячейка (%d,%d,z=%d) должна быть лестничной "
                "(%s), получено %r. to_anchor=(%d,%d), last_stair=%s, z_top=%d",
                conn_label, nb_x, nb_y, z_top - 1,
                ", ".join(sorted(_STAIR_ELEMENTS)), nb_elem,
                tx, ty, last_stair, z_top,
            )

        # ── to_anchor: system_facing соседа смотрит на to_anchor ─────────────
        if nb_elem in _STAIR_DIRECTIONAL:
            expected_facing = _V_TO_FACING.get((Vx, Vy))
            got_facing = nb_cell.system_facing if nb_cell else None
            if got_facing != expected_facing:
                logger.error(
                    "u_shape %s [to_anchor facing соседа]: ячейка (%d,%d,z=%d) "
                    "имеет system_facing=%r, ожидается %r (exit_v=(%d,%d)).",
                    conn_label, nb_x, nb_y, z_top - 1,
                    got_facing, expected_facing, Vx, Vy,
                )

    def validate(
        self,
        fr_anchor:       tuple[int, int],
        to_anchor:       tuple[int, int],
        last_stair:      tuple[int, int],
        exit_v:          tuple[int, int],
        z_lo:            int,
        z_top:           int,
        cells:           dict,
        conn_label:      str,
        shaft_footprint: set[tuple[int, int]],
        shaft_interior:  set[tuple[int, int]],
        facing:          str,
        stair_cells:     list[tuple[int, int, int]] | None = None,
        turn_vector:     tuple[int, int] | None = None,
    ) -> None:
        self._check_anchors(
            fr_anchor, to_anchor, z_lo, z_top, cells, conn_label,
            facing=facing, exit_v=exit_v, last_stair=last_stair,
            shaft_interior=shaft_interior, shaft_footprint=shaft_footprint,
        )

        # ── поворот: turn_vector ⊥ V_init ────────────────────────────────────
        Vx, Vy = _V_INIT[facing]
        if turn_vector is not None:
            self._check_turn_angle((Vx, Vy), turn_vector, conn_label)

        # ── путь: вектор каждой ступени указывает на следующий stair-элемент ──
        if stair_cells:
            self._check_stair_path(stair_cells, cells, conn_label)
