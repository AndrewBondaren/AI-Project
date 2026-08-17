"""8-way grid steps for discover (R41 / R42). Cardinal order matches relief facing."""

from __future__ import annotations

from app.dataModel.spatial.facing import (
    CARDINAL_WALL_OUTWARD_DELTA,
    Facing,
)

# Single 8-way map. Cardinals come from wall SoT; diagonals are relief Facing.
GRID_OUTWARD_DELTA: dict[Facing, tuple[int, int]] = {
    **CARDINAL_WALL_OUTWARD_DELTA,
    Facing.NORTHEAST: (1, 1),
    Facing.NORTHWEST: (-1, 1),
    Facing.SOUTHEAST: (1, -1),
    Facing.SOUTHWEST: (-1, -1),
}

# Chebyshev 1 neighbor order: cardinals (E,W,N,S) then diagonals.
EIGHT_FACINGS: tuple[Facing, ...] = (
    Facing.EAST,
    Facing.WEST,
    Facing.NORTH,
    Facing.SOUTH,
    Facing.NORTHEAST,
    Facing.NORTHWEST,
    Facing.SOUTHEAST,
    Facing.SOUTHWEST,
)
EIGHT_DELTAS: tuple[tuple[int, int], ...] = tuple(
    GRID_OUTWARD_DELTA[facing] for facing in EIGHT_FACINGS
)

DELTA_TO_FACING: dict[tuple[int, int], Facing] = {
    delta: facing for facing, delta in GRID_OUTWARD_DELTA.items()
}

CARDINAL_DELTAS: frozenset[tuple[int, int]] = frozenset(
    CARDINAL_WALL_OUTWARD_DELTA.values()
)


def facing_for_delta(delta: tuple[int, int]) -> Facing | None:
    return DELTA_TO_FACING.get((int(delta[0]), int(delta[1])))


def is_cardinal(facing: Facing) -> bool:
    return facing in CARDINAL_WALL_OUTWARD_DELTA


def tangent_axis(facing: Facing) -> str:
    """Axis along which a cardinal rim-run is consecutive: ``x`` or ``y``."""
    dx, dy = GRID_OUTWARD_DELTA[facing]
    return "y" if dx != 0 else "x"


def step_k(
    cell: tuple[int, int],
    rim: tuple[tuple[int, int], ...],
    facing: Facing,
) -> int | None:
    """Outward index ``k`` (>=1) from the matching rim cell, or None."""
    dx, dy = GRID_OUTWARD_DELTA[facing]
    cx, cy = cell
    for sx, sy in rim:
        if dx != 0 and dy == 0:
            if cy != sy or (cx - sx) * dx <= 0:
                continue
            k = (cx - sx) // dx
            if k >= 1 and sx + dx * k == cx:
                return k
        elif dy != 0 and dx == 0:
            if cx != sx or (cy - sy) * dy <= 0:
                continue
            k = (cy - sy) // dy
            if k >= 1 and sy + dy * k == cy:
                return k
        elif dx != 0 and dy != 0:
            if (cx - sx) * dx <= 0 or (cy - sy) * dy <= 0:
                continue
            kx = (cx - sx) // dx
            ky = (cy - sy) // dy
            if kx == ky and kx >= 1 and (sx + dx * kx, sy + dy * kx) == (cx, cy):
                return kx
    return None


def truncate_trace(
    trace: tuple[tuple[int, int], ...],
    rim: tuple[tuple[int, int], ...],
    facing: Facing,
    max_k: int,
) -> tuple[tuple[int, int], ...]:
    cap = max(0, int(max_k))
    return tuple(
        cell for cell in trace
        if (k := step_k(cell, rim, facing)) is not None and k <= cap
    )
