from app.application.worldData.generators.facing import Facing

_OPPOSITE: dict[str, str] = {
    Facing.NORTH: Facing.SOUTH,
    Facing.SOUTH: Facing.NORTH,
    Facing.EAST:  Facing.WEST,
    Facing.WEST:  Facing.EAST,
}

_V_INIT: dict[Facing, tuple[int, int]] = {
    Facing.NORTH: ( 0, +1),
    Facing.SOUTH: ( 0, -1),
    Facing.EAST:  (+1,  0),
    Facing.WEST:  (-1,  0),
}

_V_TO_FACING: dict[tuple[int, int], Facing] = {v: k for k, v in _V_INIT.items()}
