"""
U-shape staircase — вспомогательные функции.
ТЗ: docs/tz_staircase_generation.md §0 «Правила распределения flat»
"""
import logging
import random
from dataclasses import dataclass

from app.application.worldData.generators.structure.staircase.facingHelper import _V_INIT

_NS = frozenset({"north", "south"})

logger = logging.getLogger(__name__)


def u_shape_march_depth(shaft_depth: int) -> int:
    """march_depth для u_shape: interior_depth − 1 = (shaft_depth − 2) − 1."""
    return shaft_depth - 3


@dataclass
class UShapeParams:
    facing: str
    ax: int
    ay: int
    width_int: int
    depth_int: int
    march_depth: int       # depth−1 (used for validation only)
    march_depth_mid: int   # steps per full march (= d for NS, w for EW)
    march_count: int
    steps_march_0: int     # steps in march 0 (1..march_depth_mid); last march always march_depth_mid
    flat_per_march: int    # stair_floor cells per landing (0 for march_count=1)
    flat_march1: int       # stair_floor cells for single-march path
    turn_vector: tuple[int, int]
    fr_anchor: tuple[int, int]
    far_anchor: tuple[int, int]
    V_init: tuple[int, int]


def _compute_fr_anchor(
    ax: int, ay: int, w: int, d: int, facing: str,
    prev_fr_anchor: tuple[int, int] | None = None,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """
    Returns (fr_anchor, far_anchor, turn_vector).
    If prev_fr_anchor given, reuses the same near-side corner deterministically.
    far_anchor = diagonally opposite corner in interior.
    """
    if facing == "north":
        choices = [((ax,       ay), (+1, 0)),
                   ((ax+w-1,   ay), (-1, 0))]
    elif facing == "south":
        choices = [((ax,       ay+d-1), (+1, 0)),
                   ((ax+w-1,   ay+d-1), (-1, 0))]
    elif facing == "east":
        choices = [((ax, ay),       (0, +1)),
                   ((ax, ay+d-1),   (0, -1))]
    else:  # west
        choices = [((ax+w-1, ay),     (0, +1)),
                   ((ax+w-1, ay+d-1), (0, -1))]

    if prev_fr_anchor is not None:
        # Reuse the same near-wall corner as the previous flight's fr_anchor.
        # In a single-march U-path the last stair always lands at the OPPOSITE corner,
        # so using the same corner avoids placing the anchor on top of that last stair.
        same = [c for c in choices if c[0] == prev_fr_anchor]
        fr, tv = same[0] if same else choices[0]
    else:
        fr, tv = random.choice(choices)

    fx, fy = fr
    far = (2*ax + w-1 - fx, 2*ay + d-1 - fy)
    return fr, far, tv


def _compute_u_params(
    ax: int, ay: int, w: int, d: int, facing: str, z_height: int,
    conn_label: str = "",
    prev_fr_anchor: tuple[int, int] | None = None,
) -> UShapeParams:
    march_depth     = (d - 1) if facing in _NS else (w - 1)
    march_depth_mid = d       if facing in _NS else w

    # N path cells for single-march U-traversal
    # _NS: 3-sided path = 2*(d-1) + (w-1) + 1 = w + 2d - 2
    # _EW: 3-sided path = 2*(w-1) + (d-1) + 1 = 2w + d - 2
    N1 = (w + 2 * d - 2) if facing in _NS else (2 * w + d - 2)

    # Single-march: z_height fits inside one U-traversal.
    # Multi-march: last march is always full (march_depth_mid steps).
    # March 0 gets the remainder: steps_march_0 = (z_height−1) % march_depth_mid + 1 ∈ [1, march_depth_mid].
    # Total: steps_march_0 + (march_count−1) * march_depth_mid = z_height.
    if z_height <= N1:
        march_count   = 1
        steps_march_0 = z_height  # not used for march_count=1 path
    else:
        steps_march_0 = (z_height - 1) % march_depth_mid + 1
        march_count   = (z_height - steps_march_0) // march_depth_mid + 1

    march_cross = w if facing in _NS else d
    flat_march1 = N1 - z_height if march_count == 1 else 0
    if march_count > 1:
        if march_cross < 3:
            # TODO: fallback — автоматически выбрать ближайший валидный размер шахты
            # (min rect_standard для multi-march) или усечь z_height до N1 вместо ValueError.
            raise ValueError(
                f"u_shape {conn_label}: multi-march ({march_count} маршей) невозможен — "
                f"{'w' if facing in _NS else 'd'}={march_cross} < 3, нет средней колонны. "
                f"Увеличьте шахту или уменьшите z_height ({z_height} > N1={N1})."
            )
        flat_per_march = max(0, march_cross - 2)
    else:
        flat_per_march = 0

    fr_anchor, far_anchor, turn_vector = _compute_fr_anchor(ax, ay, w, d, facing, prev_fr_anchor)

    return UShapeParams(
        facing=facing,
        ax=ax, ay=ay,
        width_int=w, depth_int=d,
        march_depth=march_depth,
        march_depth_mid=march_depth_mid,
        march_count=march_count,
        steps_march_0=steps_march_0,
        flat_per_march=flat_per_march,
        flat_march1=flat_march1,
        turn_vector=turn_vector,
        fr_anchor=fr_anchor,
        far_anchor=far_anchor,
        V_init=_V_INIT[facing],
    )


def _compute_pseudo(
    ax: int, ay: int, w: int, d: int, facing: str, march_count: int,
) -> set[tuple[int, int]]:
    """
    Pseudo-column: interior non-perimeter cells that become void after stair placement.
    march_count==1: center block + middle cells of anchor wall.
    march_count>1:  center block only.
    """
    if w < 3 or d < 3:
        return set()
    center = {
        (ax + dx, ay + dy)
        for dx in range(1, w - 1)
        for dy in range(1, d - 1)
    }
    if march_count > 1:
        return center
    Vx0, Vy0 = _V_INIT[facing]
    if Vy0 > 0:       # facing north → anchor wall y=ay
        anchor_wall = {(ax + dx, ay) for dx in range(1, w - 1)}
    elif Vy0 < 0:     # facing south → anchor wall y=ay+d-1
        anchor_wall = {(ax + dx, ay + d - 1) for dx in range(1, w - 1)}
    elif Vx0 > 0:     # facing east → anchor wall x=ax
        anchor_wall = {(ax, ay + dy) for dy in range(1, d - 1)}
    else:              # facing west → anchor wall x=ax+w-1
        anchor_wall = {(ax + w - 1, ay + dy) for dy in range(1, d - 1)}
    return center | anchor_wall


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


def _path_intermediates(
    from_xy: tuple[int, int],
    to_xy: tuple[int, int],
    interior_set: set[tuple[int, int]],
    forbidden: set[tuple[int, int]] | None = None,
    corner_set: set[tuple[int, int]] | None = None,
    next_march_dir: tuple[int, int] | None = None,
) -> list[tuple[int, int]]:
    """
    Кратчайший direction-aware 4-связный путь от from_xy до to_xy в interior_set.
    Возвращает промежуточные ячейки (без from_xy и to_xy).

    forbidden       — позиции, которые нельзя использовать (нарушают headroom).
    corner_set      — углы шахты: линейные клетки идут прямо, угловые поворачивают ровно 90°.
    next_march_dir  — вектор следующего марша: если to_xy угловая, приход должен быть
                      перпендикулярен этому вектору (linked-list инвариант на стыке маршей).
    """
    if from_xy == to_xy:
        return []
    _forbidden = forbidden or set()
    _corners = corner_set or set()
    from collections import deque

    # Состояние BFS: (позиция, входящее_направление).
    # Одна позиция может быть посещена с разными входящими направлениями.
    _State = tuple[tuple[int, int], tuple[int, int] | None]
    start: _State = (from_xy, None)
    parent: dict[_State, _State | None] = {start: None}
    queue: deque[_State] = deque([start])
    found: _State | None = None

    while queue and found is None:
        (cx, cy), incoming = queue.popleft()
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            direction = (ddx, ddy)
            nb = (cx + ddx, cy + ddy)

            # Линейные ячейки: движение строго прямо.
            # Угловые ячейки: только поворот ровно 90° (прямой и разворот запрещены).
            if incoming is not None:
                if (cx, cy) in _corners:
                    if direction[0] * incoming[0] + direction[1] * incoming[1] != 0:
                        continue
                else:
                    if direction != incoming:
                        continue

            nb_state: _State = (nb, direction)
            if nb_state in parent:
                continue

            if nb == to_xy:
                # Linked-list инвариант на стыке маршей: если to_xy угловая и известен
                # вектор следующего марша — приход должен быть ему перпендикулярен.
                if (
                    next_march_dir is not None
                    and nb in _corners
                    and direction[0] * next_march_dir[0] + direction[1] * next_march_dir[1] != 0
                ):
                    continue
                parent[nb_state] = ((cx, cy), incoming)
                found = nb_state
                break

            if nb in interior_set and nb not in _forbidden:
                parent[nb_state] = ((cx, cy), incoming)
                queue.append(nb_state)

    if found is None:
        return []

    path: list[tuple[int, int]] = []
    cur: _State | None = found
    while cur is not None:
        path.append(cur[0])
        cur = parent[cur]
    path.reverse()
    return path[1:-1]  # исключаем from_xy и to_xy


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

    # Марш 0 всегда чётный: площадка на дальней стороне.
    # Нечётные марши заканчиваются у ближней стенки — площадка тоже там.
    # Чётные марши (>0) заканчиваются у дальней стенки.
    if march_index == 0 or march_index % 2 == 0:
        pool1 = _far_end_cells(ax, ay, w, d, facing)
        pool2 = _anchor_side_cells(ax, ay, w, d, facing)
    else:
        pool1 = _anchor_side_cells(ax, ay, w, d, facing)
        pool2 = _far_end_cells(ax, ay, w, d, facing)

    candidates.extend(pool1)
    logger.info("u_shape %s march=%d  pool1=%s", conn_label, march_index, pool1)

    if march_index == 0:
        if flat > ideal:
            side = _side_wall_cells(ax, ay, w, d, facing, turn_vector)
            candidates.extend(side)
            logger.info("u_shape %s march=%d  pool3 side_walls=%s", conn_label, march_index, side)
    else:
        if flat > ideal:
            candidates.extend(pool2)
            logger.info("u_shape %s march=%d  pool2=%s", conn_label, march_index, pool2)
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
    logger.info("u_shape %s march=%d  stair_floor -> %s", conn_label, march_index, result)
    return result
