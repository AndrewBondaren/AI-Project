"""
Staircase anchor validators.
Специфичны для конкретных типов лестниц — вызываются из соответствующих builder-классов.
"""

_FACING_NAME: dict[tuple[int, int], str] = {
    (0, +1): "north", (0, -1): "south", (+1, 0): "east", (-1, 0): "west",
}


def validate_u_shape_anchors(
    fr_anchor: tuple[int, int],
    to_anchor: tuple[int, int],
    last_stair: tuple[int, int],
    exit_v: tuple[int, int],
    z_lo: int,
    z_top: int,
    cells: dict,
    conn_label: str,
) -> None:
    """
    Валидация якорей для u_shape лестницы.

    fr_anchor: первая ступень (stair_anchor) на z_lo.
    to_anchor: floor-ячейка в комнате назначения на z_top,
               примыкающая к последней ступени строго по направлению exit_v.
    """
    fx, fy = fr_anchor
    tx, ty = to_anchor
    lx, ly = last_stair
    vx, vy = exit_v

    fr_cell = cells.get((fx, fy, z_lo))
    if fr_cell is None or fr_cell.system_building_element != "stair_anchor":
        got = fr_cell.system_building_element if fr_cell else "пусто"
        raise ValueError(
            f"u_shape {conn_label}: якорь входа ({fx},{fy},z={z_lo}) "
            f"должен быть stair_anchor, получено {got!r}"
        )

    to_cell = cells.get((tx, ty, z_top))
    if to_cell is None or to_cell.system_building_element != "floor":
        got = to_cell.system_building_element if to_cell else "пусто"
        raise ValueError(
            f"u_shape {conn_label}: якорь выхода ({tx},{ty},z={z_top}) "
            f"должен быть floor, получено {got!r}"
        )

    expected_tx, expected_ty = lx + vx, ly + vy
    if (tx, ty) != (expected_tx, expected_ty):
        dir_name = _FACING_NAME.get((vx, vy), f"({vx},{vy})")
        raise ValueError(
            f"u_shape {conn_label}: якорь выхода ({tx},{ty}) не примыкает к последней "
            f"ступени ({lx},{ly}) по направлению {dir_name!r}; "
            f"ожидалось ({expected_tx},{expected_ty})"
        )
