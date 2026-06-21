"""
Vertical ladder staircase — вспомогательные функции.
ТЗ: docs/tz_staircase_generation.md §8
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.application.worldData.generators.structure.cellBuilder import _interior
from app.application.worldData.generators.facing import Facing
from app.application.worldData.generators.structure.structureElement import (
    StructureElement, _WALL_ELEMENTS, _PASSABLE_ELEMENTS,
)
from app.application.worldData.generators.structure.roomInstance import _RoomInstance

logger = logging.getLogger(__name__)

_DOOR_ELEMENTS: frozenset[StructureElement] = frozenset({StructureElement.DOOR})
_NEIGHBORS      = ((1, 0), (-1, 0), (0, 1), (0, -1))

# north=+y, south=-y, east=+x, west=-x (соответствует shaftPlacer.py)
_FACING_VEC: dict[Facing, tuple[int, int]] = {
    Facing.NORTH: (0,  1),
    Facing.SOUTH: (0, -1),
    Facing.EAST:  (1,  0),
    Facing.WEST:  (-1, 0),
}


@dataclass
class VerticalLadderParams:
    anchor:       tuple[int, int]           # XY-позиция лестницы; fr_anchor == to_anchor
    is_movable:   bool
    has_trapdoor: bool                       # физический люк на z_top
    has_walls:       bool          = False   # стены вокруг столба (3 стороны, кроме entry)
    facing:          str | None    = None    # направление «наружу» (для has_walls)
    open_wall_shaft: str | None    = None    # материал окна в стенах шахты; None → глухие стены


def _is_corner_cell(
    wx: int, wy: int,
    fr_wall: set[tuple[int, int]],
    exclude: tuple[int, int],
) -> bool:
    """Угловая ячейка периметра — имеет соседей-периметр по обеим осям (не считая интерьер)."""
    wall_nb = [
        (wx + ddx, wy + ddy)
        for ddx, ddy in _NEIGHBORS
        if (wx + ddx, wy + ddy) in fr_wall
        and (wx + ddx, wy + ddy) != exclude
    ]
    return any(nx != wx for nx, ny in wall_nb) and any(ny != wy for nx, ny in wall_nb)


def _has_adjacent(x: int, y: int, z: int, cells: dict, elements: set[str]) -> bool:
    return any(
        (cell := cells.get((x + dx, y + dy, z))) is not None
        and cell.system_building_element in elements
        for dx, dy in _NEIGHBORS
    )


def _has_stair_anchor_nearby(x: int, y: int, z: int, cells: dict) -> bool:
    """Есть ли STAIR_ANCHOR в радиусе 1 ячейки (включая саму ячейку) на уровне z."""
    for dx, dy in ((0, 0), *_NEIGHBORS):
        cell = cells.get((x + dx, y + dy, z))
        if cell and cell.system_building_element == StructureElement.STAIR_ANCHOR:
            return True
    return False



def _compute_vertical_ladder_anchor(
    fr:             _RoomInstance,
    to:             _RoomInstance,
    cells:          dict,
    z_lo:           int,
    z_top:          int,
    near_wall:      bool,
    on_the_edge:    bool,
    passage_height: int,
    facing:         str | None = None,
    is_movable:     bool = False,
) -> tuple[int, int]:
    """
    on_the_edge=True  — якорь снаружи fr; facing задаёт сторону.
    near_wall=True    — якорь внутри, допускает соседство со стенами.
    default           — якорь внутри, без стен и дверей рядом.
    """
    if on_the_edge:
        # Якорь снаружи верхней комнаты (to) — fr=нижняя после нормализации в базовом классе
        return _anchor_outside(to, fr, cells, z_lo, z_top, facing=facing, is_movable=is_movable)

    fr_int = set(_interior(fr.get_footprint()))
    to_int = set(_interior(to.get_footprint()))
    candidates = fr_int & to_int

    if not candidates:
        logger.warning(
            "vertical_ladder: interior %r и %r не пересекаются — используем interior нижней комнаты",
            fr.room_id, to.room_id,
        )
        candidates = fr_int or set(fr.get_footprint())

    valid = []
    for x, y in candidates:
        if _has_adjacent(x, y, z_lo, cells, _DOOR_ELEMENTS):
            continue
        if not near_wall and _has_adjacent(x, y, z_lo, cells, _WALL_ELEMENTS):
            continue
        cell_lo = cells.get((x, y, z_lo))
        if cell_lo is None or cell_lo.system_building_element != StructureElement.FLOOR:
            continue
        cell_top = cells.get((x, y, z_top))
        if cell_top is None or cell_top.system_building_element != StructureElement.FLOOR:
            continue
        if any(
            (c := cells.get((x, y, z_top + dz))) is not None
            and c.system_building_element not in _PASSABLE_ELEMENTS
            for dz in range(1, passage_height + 1)
        ):
            continue
        if _has_stair_anchor_nearby(x, y, z_lo, cells):
            continue
        if _has_stair_anchor_nearby(x, y, z_top, cells):
            continue
        valid.append((x, y))

    if not valid:
        logger.warning(
            "vertical_ladder %r→%r: нет кандидатов после фильтрации (near_wall=%s) — "
            "берём SW-угол без фильтрации",
            fr.room_id, to.room_id, near_wall,
        )
        valid = sorted(candidates)

    xs = [x for x, _ in valid]
    ys = [y for _, y in valid]
    return (min(xs), min(ys))


def _anchor_outside(
    fr:         _RoomInstance,
    to:         _RoomInstance,
    cells:      dict,
    z_lo:       int,
    z_top:      int,
    facing:     str | None = None,
    is_movable: bool = False,
) -> tuple[int, int]:
    """
    Якорь — одна ячейка снаружи fr.

    facing задаёт в каком направлении смотреть (north/south/east/west).
    Если facing=None — выбирается любая свободная сторона.
    Предпочтение — wall-ячейки, пересекающие XY footprint to.
    Для фиксированных лестниц (not is_movable) угловые позиции исключаются.
    """
    fr_fp   = fr.get_footprint()
    fr_int  = set(_interior(fr_fp))
    to_fp   = to.get_footprint()
    fr_wall = fr_fp - fr_int

    facing_vec = _FACING_VEC.get(Facing(facing)) if facing else None

    candidates: list[tuple[tuple[int, int], tuple[int, int]]] = []  # (wall_xy, outside_xy)
    for wx, wy in fr_wall:
        for dx, dy in _NEIGHBORS:
            ox, oy = wx + dx, wy + dy
            if (ox, oy) in fr_fp:
                continue
            if facing_vec and (dx, dy) != facing_vec:
                continue
            cell_lo = cells.get((ox, oy, z_lo))
            if cell_lo and cell_lo.system_building_element in _WALL_ELEMENTS | _DOOR_ELEMENTS:
                continue
            if cells.get((ox, oy, z_top)) is not None:
                continue
            if _has_stair_anchor_nearby(ox, oy, z_top, cells):
                continue
            if not is_movable and _is_corner_cell(wx, wy, fr_wall, (ox, oy)):
                continue
            candidates.append(((wx, wy), (ox, oy)))

    if not candidates:
        logger.warning(
            "vertical_ladder on_the_edge %r (facing=%r): нет свободной внешней позиции — fallback SW interior",
            fr.room_id, facing,
        )
        fallback = sorted(fr_int)
        return fallback[0]

    preferred = [
        (wall, outside) for wall, outside in candidates
        if wall in to_fp or outside in to_fp
    ]
    pool = preferred or candidates

    xs = [ox for _, (ox, _) in pool]
    ys = [oy for _, (_, oy) in pool]
    target_x, target_y = min(xs), min(ys)
    for _, (ox, oy) in pool:
        if ox == target_x and oy == target_y:
            return (ox, oy)
    return pool[0][1]


def _compute_vertical_ladder_params(
    fr:              _RoomInstance,
    to:              _RoomInstance,
    cells:           dict,
    z_lo:            int,
    z_top:           int,
    is_movable:      bool,
    has_trapdoor:    bool,
    near_wall:       bool,
    on_the_edge:     bool,
    passage_height:  int,
    has_walls:       bool       = False,
    facing:          str | None = None,
    open_wall_shaft: str | None = None,
) -> VerticalLadderParams:
    anchor = _compute_vertical_ladder_anchor(
        fr, to, cells, z_lo, z_top, near_wall, on_the_edge,
        passage_height=passage_height, facing=facing, is_movable=is_movable,
    )
    return VerticalLadderParams(
        anchor=anchor, is_movable=is_movable,
        has_trapdoor=has_trapdoor, has_walls=has_walls, facing=facing,
        open_wall_shaft=open_wall_shaft,
    )
