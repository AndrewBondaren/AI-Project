"""
U-shape staircase — вспомогательные функции.
ТЗ: docs/tz_staircase_generation.md §0 «Правила распределения flat»
"""
import logging


def u_shape_march_depth(shaft_depth: int) -> int:
    """march_depth для u_shape: interior_depth − 1 = (shaft_depth − 2) − 1."""
    return shaft_depth - 3

logger = logging.getLogger(__name__)


def _center_first(row: list[tuple[int, int]]) -> list[tuple[int, int]]:
    n = len(row)
    mid = n // 2
    if n % 2 == 1:
        ordered = [row[mid]]
        for i in range(1, mid + 1):
            if mid - i >= 0:
                ordered.append(row[mid - i])
            if mid + i < n:
                ordered.append(row[mid + i])
    else:
        ordered = [row[mid - 1], row[mid]]
        for i in range(1, mid):
            ordered.append(row[mid - 1 - i])
            ordered.append(row[mid + i])
    return ordered


def _far_end_cells(
    ax: int, ay: int, w: int, d: int, facing: str,
) -> list[tuple[int, int]]:
    """Дальняя стена шахты (to_room side), от центра к краям."""
    if facing == "north":
        row = [(ax + x, ay + d - 1) for x in range(w)]
    elif facing == "south":
        row = [(ax + x, ay) for x in range(w)]
    elif facing == "east":
        row = [(ax + w - 1, ay + y) for y in range(d)]
    else:  # west
        row = [(ax, ay + y) for y in range(d)]
    return _center_first(row)


def _anchor_side_cells(
    ax: int, ay: int, w: int, d: int, facing: str,
) -> list[tuple[int, int]]:
    """
    Ближняя стена шахты (fr_room side), от центра к краям.
    Вход и выход U-образной лестницы находятся на этой стене в противоположных углах.
    """
    if facing == "north":
        row = [(ax + x, ay) for x in range(w)]
    elif facing == "south":
        row = [(ax + x, ay + d - 1) for x in range(w)]
    elif facing == "east":
        row = [(ax, ay + y) for y in range(d)]
    else:  # west
        row = [(ax + w - 1, ay + y) for y in range(d)]
    return _center_first(row)


def _side_wall_cells(
    ax: int, ay: int, w: int, d: int, facing: str,
    turn_vector: tuple[int, int],
) -> list[tuple[int, int]]:
    """
    Боковые стены шахты (без far end и anchor side), от far end к near end,
    turn_vector сторона первой внутри каждого шага.
    N/S: d-2 ячеек на каждой боковой стене. E/W: w-2 ячеек.
    """
    tvx, tvy = turn_vector
    result: list[tuple[int, int]] = []

    if facing in ("north", "south"):
        tv_x  = ax + w - 1 if tvx > 0 else ax
        opp_x = ax         if tvx > 0 else ax + w - 1
        for step in range(d - 2):
            y = (ay + d - 2 - step) if facing == "north" else (ay + 1 + step)
            result.append((tv_x,  y))
            result.append((opp_x, y))
    else:  # east / west
        tv_y  = ay + d - 1 if tvy > 0 else ay
        opp_y = ay         if tvy > 0 else ay + d - 1
        for step in range(w - 2):
            x = (ax + w - 2 - step) if facing == "east" else (ax + 1 + step)
            result.append((x, tv_y))
            result.append((x, opp_y))
    return result


def flat_positions(
    flat: int,
    ax: int, ay: int, w: int, d: int,
    facing: str,
    turn_vector: tuple[int, int],
    march_index: int,
    conn_label: str = "",
) -> list[tuple[int, int]]:
    """
    Возвращает упорядоченный список (x, y) для stair_floor по правилам приоритета ТЗ §0.

    Марш 1 (march_index=0): near wall — pseudo-column, Pool 2 пропускается.
      flat ≤ ideal  → Pool 1 (far end)
      flat > ideal  → Pool 1 + Pool 3 (боковые стены)

    Марши 2+ (march_index>0): стандартный порядок.
      flat ≤ ideal     → Pool 1
      flat ≤ mid_ideal → Pool 1 + Pool 2 (anchor side)
      flat > mid_ideal → Pool 1 + Pool 2 + Pool 3
    """
    if flat <= 0:
        logger.info("u_shape %s march=%d: flat=0, nothing to place", conn_label, march_index)
        return []

    is_ns     = facing in ("north", "south")
    far_sz    = w if is_ns else d
    lat       = (d - 2) if is_ns else (w - 2)
    ideal     = far_sz
    mid_ideal = far_sz * 2
    optimal   = far_sz + 2 * lat

    logger.info(
        "u_shape %s march=%d flat=%d  ideal=%d mid_ideal=%d optimal=%d  facing=%s turn_v=%s",
        conn_label, march_index, flat, ideal, mid_ideal, optimal, facing, turn_vector,
    )

    candidates: list[tuple[int, int]] = []

    far_end = _far_end_cells(ax, ay, w, d, facing)
    candidates.extend(far_end)
    logger.info("u_shape %s march=%d  pool1 far_end=%s", conn_label, march_index, far_end)

    if march_index == 0:
        if flat > ideal:
            side = _side_wall_cells(ax, ay, w, d, facing, turn_vector)
            candidates.extend(side)
            logger.info("u_shape %s march=%d  pool3 side_walls=%s", conn_label, march_index, side)
    else:
        if flat > ideal:
            anchor = _anchor_side_cells(ax, ay, w, d, facing)
            candidates.extend(anchor)
            logger.info("u_shape %s march=%d  pool2 anchor_side=%s", conn_label, march_index, anchor)
        if flat > mid_ideal:
            side = _side_wall_cells(ax, ay, w, d, facing, turn_vector)
            candidates.extend(side)
            logger.info("u_shape %s march=%d  pool3 side_walls=%s", conn_label, march_index, side)

    result = candidates[:flat]
    if len(result) < flat:
        logger.warning(
            "u_shape %s march=%d: только %d позиций для flat=%d — шахта слишком мала",
            conn_label, march_index, len(result), flat,
        )
    logger.info("u_shape %s march=%d  stair_floor → %s", conn_label, march_index, result)
    return result
