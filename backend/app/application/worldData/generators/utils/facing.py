from enum import Enum


class Facing(str, Enum):
    """Сторона света / грань bbox. Единый тип для участков, зданий и графа дорог."""
    NORTH      = "north"
    SOUTH      = "south"
    EAST       = "east"
    WEST       = "west"
    NORTHEAST  = "north_east"
    NORTHWEST  = "north_west"
    SOUTHEAST  = "south_east"
    SOUTHWEST  = "south_west"

    def __str__(self) -> str:
        return self.value


CARDINAL_FACINGS: frozenset[Facing] = frozenset({
    Facing.NORTH, Facing.SOUTH, Facing.EAST, Facing.WEST,
})

INTERCARDINAL_FACINGS: frozenset[Facing] = frozenset({
    Facing.NORTHEAST, Facing.NORTHWEST, Facing.SOUTHEAST, Facing.SOUTHWEST,
})

OPPOSITE: dict[Facing, Facing] = {
    Facing.NORTH:     Facing.SOUTH,
    Facing.SOUTH:     Facing.NORTH,
    Facing.EAST:      Facing.WEST,
    Facing.WEST:      Facing.EAST,
    Facing.NORTHEAST: Facing.SOUTHWEST,
    Facing.NORTHWEST: Facing.SOUTHEAST,
    Facing.SOUTHEAST: Facing.NORTHWEST,
    Facing.SOUTHWEST: Facing.NORTHEAST,
}

# legacy compact labels (TZ v1 roads) → canonical Facing
_COMPACT: dict[str, Facing] = {
    "N": Facing.NORTH,
    "S": Facing.SOUTH,
    "E": Facing.EAST,
    "W": Facing.WEST,
    "NE": Facing.NORTHEAST,
    "NW": Facing.NORTHWEST,
    "SE": Facing.SOUTHEAST,
    "SW": Facing.SOUTHWEST,
}


def parse_facing(value: str | Facing | None) -> Facing | None:
    if value is None:
        return None
    if isinstance(value, Facing):
        return value
    key = value.strip()
    if key in _COMPACT:
        return _COMPACT[key]
    return Facing(key)


def opposite(facing: Facing) -> Facing:
    return OPPOSITE[facing]


def is_meridional_edge(facing: Facing) -> bool:
    """Грань с нормалью по оси N–S (snap col, фикс row)."""
    return facing in (Facing.NORTH, Facing.SOUTH)


def is_latitudinal_edge(facing: Facing) -> bool:
    """Грань с нормалью по оси E–W (snap row, фикс col)."""
    return facing in (Facing.EAST, Facing.WEST)


def is_corner(facing: Facing) -> bool:
    return facing in INTERCARDINAL_FACINGS


def snap_bbox_edge_to_grid(
    facing:   Facing,
    rel_x:    int,
    rel_y:    int,
    step_x:   int,
    step_y:   int,
    n_cols:   int,
    n_rows:   int,
) -> tuple[int, int]:
    """
    (col, row) узла сетки на грани/углу bbox района.
    y↑ = north; south = row 0, north = row n_rows-1.
    """
    if is_corner(facing):
        col = n_cols - 1 if facing in (Facing.NORTHEAST, Facing.SOUTHEAST) else 0
        row = n_rows - 1 if facing in (Facing.NORTHEAST, Facing.NORTHWEST) else 0
        return col, row

    if is_meridional_edge(facing):
        col = max(0, min(n_cols - 1, round(rel_x / step_x)))
        row = 0 if facing == Facing.SOUTH else n_rows - 1
        return col, row

    col = n_cols - 1 if facing == Facing.EAST else 0
    row = max(0, min(n_rows - 1, round(rel_y / step_y)))
    return col, row
