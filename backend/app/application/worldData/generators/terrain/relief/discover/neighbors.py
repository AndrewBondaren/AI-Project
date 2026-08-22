"""8-way grid steps for discover (R41 / R42). Cardinal order matches relief facing."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence

from app.dataModel.spatial.facing import (
    CARDINAL_WALL_OUTWARD_DELTA,
    GRID_DELTA_TO_FACING,
    GRID_OUTWARD_DELTA,
    Facing,
)

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
FACING_BIT: dict[Facing, int] = {
    facing: 1 << i for i, facing in enumerate(EIGHT_FACINGS)
}

DELTA_TO_FACING: dict[tuple[int, int], Facing] = GRID_DELTA_TO_FACING

CARDINAL_DELTAS: frozenset[tuple[int, int]] = frozenset(
    CARDINAL_WALL_OUTWARD_DELTA.values()
)


def iter_body_eight_views(
    body: Mapping[tuple[int, int], int],
    z_at: Callable[[tuple[int, int]], int | None],
) -> Iterator[tuple[tuple[int, int], Facing, tuple[int, int], int, int]]:
    """Vertex body × 8: ``(src, facing, neighbor, z_src, z_nb)`` when neighbor z exists.

    Same 8-look leftover rim shots use. Caller filters which views fire.
    """
    for (x, y), z_body in body.items():
        src = (int(x), int(y))
        z_src = int(z_body)
        for facing in EIGHT_FACINGS:
            dx, dy = GRID_OUTWARD_DELTA[facing]
            nb = (src[0] + dx, src[1] + dy)
            zn = z_at(nb)
            if zn is None:
                continue
            yield src, facing, nb, z_src, int(zn)


def facing_for_delta(delta: tuple[int, int]) -> Facing | None:
    return DELTA_TO_FACING.get((int(delta[0]), int(delta[1])))


def is_local_min(surface, xy: tuple[int, int]) -> bool:
    """True if no 8-neighbor is strictly lower (C41 shared-pit / R36t bottom)."""
    from app.application.worldData.generators.terrain.relief.discover.types import (
        cell_z,
    )

    z = cell_z(surface, xy)
    if z is None:
        return False
    x, y = xy
    for dx, dy in EIGHT_DELTAS:
        zn = cell_z(surface, (x + dx, y + dy))
        if zn is not None and zn < z:
            return False
    return True


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


def max_outward_k(
    cells: Sequence[tuple[int, int]],
    rim: tuple[tuple[int, int], ...],
    facing: Facing,
) -> int:
    """Max outward ``k`` in ``cells`` (C41 corridor / paint L). ``0`` if empty."""
    best = 0
    for cell in cells:
        k = step_k(cell, rim, facing)
        if k is not None and k > best:
            best = k
    return best


def cell_at_max_outward_k(
    cells: Sequence[tuple[int, int]],
    rim: tuple[tuple[int, int], ...],
    facing: Facing,
) -> tuple[int, int] | None:
    """Cell at the largest outward ``k`` (last on ties)."""
    best_cell: tuple[int, int] | None = None
    best_k = 0
    for cell in cells:
        k = step_k(cell, rim, facing)
        if k is not None and (best_cell is None or k >= best_k):
            best_k = k
            best_cell = cell
    return best_cell
