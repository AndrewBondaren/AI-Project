"""Measure outward ``free_gap`` until obstacle — tz_terrain_relief R36m/n §9."""

from __future__ import annotations

from collections.abc import Callable

Coord = tuple[int, int]
BlockedFn = Callable[[Coord], bool]


def measure_free_gap(
    *,
    start: Coord,
    outward: tuple[int, int],
    is_blocked: BlockedFn,
    max_scan: int = 64,
) -> int:
    """Count consecutive free cells from ``start`` along ``outward``.

    ``gap == 0`` if ``start`` itself is blocked (or invalid outward).
    Stops at first blocked cell; does not count that cell.
    """
    dx, dy = int(outward[0]), int(outward[1])
    if (dx, dy) == (0, 0) or (abs(dx) + abs(dy) != 1):
        return 0
    limit = max(0, int(max_scan))
    x, y = int(start[0]), int(start[1])
    gap = 0
    for _ in range(limit):
        cell = (x, y)
        if is_blocked(cell):
            break
        gap += 1
        x += dx
        y += dy
    return gap
