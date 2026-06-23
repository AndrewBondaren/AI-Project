"""
Shared helpers for passage builders.
"""
import uuid

from app.application.worldData.generators.facing import Facing
from app.application.worldData.generators.structure.roomInstance import _RoomInstance

_WALL_DIRS: dict[Facing, tuple[int, int]] = {
    Facing.SOUTH: (0, -1),
    Facing.NORTH: (0,  1),
    Facing.EAST:  (1,  0),
    Facing.WEST:  (-1, 0),
}


def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


def _shared_segment(r1: _RoomInstance, r2: _RoomInstance) -> list[tuple[int, int]]:
    shared = r1.get_footprint() & r2.get_footprint()
    return sorted(shared)


def _center_slice(cells: list[tuple[int, int]], width: int) -> list[tuple[int, int]]:
    n = len(cells)
    if width >= n:
        return cells
    mid = n // 2
    half = width // 2
    start = mid - half
    return cells[start: start + width]


def _doorway_facing(shared: list[tuple[int, int]]) -> Facing:
    """Return facing axis for a doorway in the given shared wall segment.

    Horizontal wall (all cells same y) → NORTH (walk along y-axis).
    Vertical wall (all cells same x) → EAST (walk along x-axis).
    """
    if len(shared) < 2:
        return Facing.NORTH
    ys = {y for _, y in shared}
    return Facing.NORTH if len(ys) == 1 else Facing.EAST


_DIRECTION_FACING: dict[str, Facing] = {
    "north": Facing.NORTH,
    "south": Facing.SOUTH,
    "east":  Facing.EAST,
    "west":  Facing.WEST,
}


def _exterior_cells_on_wall(
    room: _RoomInstance,
    direction: str,
    all_union: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    dx, dy = _WALL_DIRS[direction]
    fp = room.get_footprint()
    result: set[tuple[int, int]] = set()
    for (x, y) in fp:
        nb = (x + dx, y + dy)
        if nb not in all_union:
            result.add((x, y))
    return sorted(result)
