"""Terrain-voxel descent ray — tz_terrain_relief R37 (open_land noise).

Not R36m obstacle clearance (buildings / roads). Stops when a voxel blocks
further downhill: missing cell, z >= peak, or z >= previous (ascent / landing).
"""

from __future__ import annotations

from collections.abc import Callable

Coord = tuple[int, int]
ZAt = Callable[[Coord], int | None]

# First-step |dz| <= this stays as the heightmap (4→3 at L=1 is 45°, ok).
TERRAIN_RAY_MIN_ABS_DZ = 2


def measure_terrain_descent(
    *,
    start: Coord,
    outward: tuple[int, int],
    z_peak: int,
    z_at: ZAt,
    max_scan: int = 64,
) -> tuple[int, int]:
    """Walk ``start`` along ``outward`` until a voxel blocks.

    Returns ``(L, z_end)``. ``L == 0`` if the first cell is already blocked.
    ``z_end`` is the last free cell (``z_peak`` when L=0).
    """
    dx, dy = int(outward[0]), int(outward[1])
    if (dx, dy) == (0, 0) or (abs(dx) + abs(dy) != 1):
        return 0, int(z_peak)
    peak = int(z_peak)
    x, y = int(start[0]), int(start[1])
    z_prev = peak
    length = 0
    z_end = peak
    for _ in range(max(0, int(max_scan))):
        z = z_at((x, y))
        if z is None or int(z) >= peak or int(z) >= z_prev:
            break
        length += 1
        z_end = int(z)
        z_prev = z_end
        x += dx
        y += dy
    return length, z_end
