"""Walk a grid ray along Facing — C21 / connections §5.1.1.

Origin is not in the trace. ``stop(cell, k)`` is inclusive: the triggering cell
is included, then the walk halts.
"""

from __future__ import annotations

from collections.abc import Callable

from app.dataModel.spatial.facing import GRID_OUTWARD_DELTA, Facing

Coord = tuple[int, int]
StopFn = Callable[[Coord, int], bool]


def walk_grid_ray(
    origin: Coord,
    facing: Facing,
    *,
    max_k: int,
    stop: StopFn | None = None,
) -> tuple[Coord, ...]:
    """Cells at k=1,2,… along ``facing`` from ``origin`` (origin excluded)."""
    delta = GRID_OUTWARD_DELTA.get(facing)
    if delta is None:
        return ()
    dx, dy = delta
    n = max(0, int(max_k))
    x, y = int(origin[0]), int(origin[1])
    cells: list[Coord] = []
    for k in range(1, n + 1):
        x += dx
        y += dy
        cell = (x, y)
        cells.append(cell)
        if stop is not None and stop(cell, k):
            break
    return tuple(cells)
