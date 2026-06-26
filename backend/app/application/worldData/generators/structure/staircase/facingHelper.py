from app.application.worldData.generators.utils.facing import Facing, parse_facing

# Лестницы: march / entry только по 4 сторонам (без intercardinal).
_OPPOSITE: dict[Facing, Facing] = {
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


def opposite(facing: Facing | str) -> Facing:
    """Entry-сторона shaft = opposite(march facing). Только N/S/E/W."""
    f = parse_facing(facing)
    if f is None:
        raise ValueError(f"invalid facing: {facing!r}")
    return _OPPOSITE[f]
