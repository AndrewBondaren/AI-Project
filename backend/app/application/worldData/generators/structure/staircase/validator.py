"""
Staircase validators — абстракция + реализации по типу лестницы.
"""
import logging
from abc import ABC, abstractmethod

from app.application.worldData.generators.structure.staircase.facingHelper import (
    _V_INIT, _V_TO_FACING,
)

logger = logging.getLogger(__name__)

_STAIR_ELEMENTS = {"staircase", "stair_anchor", "stair_floor"}
_STAIR_DIRECTIONAL = {"staircase", "stair_anchor"}


class StaircaseValidator(ABC):
    @abstractmethod
    def validate(self, **kwargs) -> None: ...


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
    ) -> None:
        fx, fy = fr_anchor
        tx, ty = to_anchor
        Vx, Vy = _V_INIT[facing]

        # ── fr_anchor: stair_anchor на z_lo ──────────────────────────────────
        fr_cell = cells.get((fx, fy, z_lo))
        got = fr_cell.system_building_element if fr_cell else "пусто"
        if got != "stair_anchor":
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

        # ── to_anchor: floor вне interior шахты ──────────────────────────────
        to_cell = cells.get((tx, ty, z_top))
        got_to = to_cell.system_building_element if to_cell else "пусто"
        if got_to != "floor":
            logger.error(
                "u_shape %s [to_anchor тип]: ячейка (%d,%d,z=%d) должна быть 'floor', "
                "получено %r. to_anchor=%s, z_top=%d, facing=%r",
                conn_label, tx, ty, z_top, got_to, to_anchor, z_top, facing,
            )
        if (tx, ty) in shaft_interior:
            xs = sorted({x for x, _ in shaft_interior})
            ys = sorted({y for _, y in shaft_interior})
            logger.error(
                "u_shape %s [to_anchor interior]: якорь выхода (%d,%d) внутри interior шахты. "
                "interior x=%d..%d, y=%d..%d",
                conn_label, tx, ty, xs[0], xs[-1], ys[0], ys[-1],
            )

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
