"""
Staircase validators — абстракция + реализации по типу лестницы.
"""
from abc import ABC, abstractmethod

_V_INIT: dict[str, tuple[int, int]] = {
    "north": (0, +1), "south": (0, -1),
    "east":  (+1,  0), "west":  (-1,  0),
}

_STAIR_ELEMENTS = {"staircase", "stair_anchor", "stair_floor"}


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
        - floor вне footprint шахты
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
            raise ValueError(
                f"u_shape {conn_label}: якорь входа ({fx},{fy},z={z_lo}) "
                f"должен быть stair_anchor, получено {got!r}"
            )

        # ── fr_anchor: внутри interior шахты ─────────────────────────────────
        if (fx, fy) not in shaft_interior:
            raise ValueError(
                f"u_shape {conn_label}: якорь входа ({fx},{fy}) "
                f"должен находиться внутри interior шахты лестницы"
            )

        # ── fr_anchor: near-side (первый марш идёт в сторону facing) ─────────
        # facing=north (Vy>0) → fr_anchor на min y interior
        # facing=south (Vy<0) → fr_anchor на max y interior
        # facing=east  (Vx>0) → fr_anchor на min x interior
        # facing=west  (Vx<0) → fr_anchor на max x interior
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
            raise ValueError(
                f"u_shape {conn_label}: якорь входа ({fx},{fy}) должен быть на "
                f"ближней стороне шахты ({axis}={val}) для facing={facing!r}, "
                f"получено {axis}={coord}"
            )

        # ── to_anchor: floor вне footprint шахты ─────────────────────────────
        to_cell = cells.get((tx, ty, z_top))
        got_to = to_cell.system_building_element if to_cell else "пусто"
        if got_to != "floor":
            raise ValueError(
                f"u_shape {conn_label}: якорь выхода ({tx},{ty},z={z_top}) "
                f"должен быть floor, получено {got_to!r}"
            )
        if (tx, ty) in shaft_footprint:
            raise ValueError(
                f"u_shape {conn_label}: якорь выхода ({tx},{ty}) "
                f"не должен находиться внутри шахты лестницы"
            )

        # ── to_anchor: сосед противоположной facing на z_top-1 — staircase ───
        nb_x, nb_y = tx - Vx, ty - Vy
        nb_cell = cells.get((nb_x, nb_y, z_top - 1))
        nb_elem = nb_cell.system_building_element if nb_cell else "пусто"
        if nb_elem not in _STAIR_ELEMENTS:
            raise ValueError(
                f"u_shape {conn_label}: сосед якоря выхода ({nb_x},{nb_y},z={z_top - 1}) "
                f"со стороны противоположной facing={facing!r} должен быть лестничной ячейкой "
                f"({', '.join(sorted(_STAIR_ELEMENTS))}), получено {nb_elem!r}"
            )
