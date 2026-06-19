"""
Base staircase validator — ABC + universal checks.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StaircaseValidator(ABC):

    def _check_to_anchor(
        self,
        cells: dict,
        to_anchor: tuple[int, int],
        z_top: int,
        shaft_interior: set[tuple[int, int]],
        shaft_footprint: set[tuple[int, int]],
        conn_label: str,
    ) -> None:
        tx, ty = to_anchor
        to_cell = cells.get((tx, ty, z_top))
        got = to_cell.system_building_element if to_cell else "пусто"

        if got != "floor":
            logger.error(
                "%s [to_anchor тип]: ячейка (%d,%d,z=%d) должна быть 'floor', получено %r.",
                conn_label, tx, ty, z_top, got,
            )
            external_floor = [
                (ex, ey)
                for (fx, fy) in shaft_footprint
                for ex, ey in ((fx + 1, fy), (fx - 1, fy), (fx, fy + 1), (fx, fy - 1))
                if (ex, ey) not in shaft_footprint
                if (c := cells.get((ex, ey, z_top)))
                and c.system_building_element == "floor"
            ]
            if external_floor:
                logger.error(
                    "%s [лестница без якоря выхода]: рядом с шахтой есть floor на z=%d %s, "
                    "но to_anchor (%d,%d) не ведёт туда (%r).",
                    conn_label, z_top, external_floor[:3], tx, ty, got,
                )

        if (tx, ty) in shaft_interior:
            xs = sorted({x for x, _ in shaft_interior})
            ys = sorted({y for _, y in shaft_interior})
            logger.error(
                "%s [to_anchor interior]: якорь выхода (%d,%d) внутри interior шахты. "
                "interior x=%d..%d, y=%d..%d",
                conn_label, tx, ty, xs[0], xs[-1], ys[0], ys[-1],
            )

    def _check_turn_angle(
        self,
        v_march: tuple[int, int],
        v_turn: tuple[int, int],
        conn_label: str,
    ) -> None:
        mx, my = v_march
        tx, ty = v_turn
        dot = mx * tx + my * ty
        if dot > 0:
            logger.error(
                "%s [поворот]: turn_vector=(%d,%d) совпадает с направлением марша (%d,%d) "
                "— поворот 0° не допускается",
                conn_label, tx, ty, mx, my,
            )
        elif dot < 0:
            logger.error(
                "%s [поворот]: turn_vector=(%d,%d) противоположен направлению марша (%d,%d) "
                "— поворот 180° не допускается",
                conn_label, tx, ty, mx, my,
            )

    @abstractmethod
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
        """
        Проверяет наличие и корректность местоположения fr_anchor и to_anchor.
        Вызывается первым в validate() каждого субкласса.
        """
        ...

    @abstractmethod
    def _check_stair_path(
        self,
        stair_cells: list[tuple[int, int, int]],
        cells: dict,
        conn_label: str,
    ) -> None: ...

    @abstractmethod
    def validate(self, **kwargs) -> None: ...
