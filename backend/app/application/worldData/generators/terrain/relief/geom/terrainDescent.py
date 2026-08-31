"""Terrain-voxel descent ray — tz_terrain_relief R37 (open_land noise).

Not R36m obstacle clearance (buildings / roads). Stops when a voxel blocks
further downhill: missing cell, z >= peak, or z >= previous (ascent / landing).

Walk is ``walk_grid_ray`` plus this mill ``stop``; area assemblers do not import here.
"""

from __future__ import annotations

from collections.abc import Callable

from app.application.worldData.generators.coordinates.gridRay import walk_grid_ray
from app.dataModel.spatial.facing import GRID_DELTA_TO_FACING

Coord = tuple[int, int]
ZHeightMap = Callable[[Coord], int | None]

# First-step |dz| <= this stays as the heightmap (4→3 at L=1 is 45°, ok).
TERRAIN_RAY_MIN_ABS_DZ = 2


def measure_terrain_descent(
    *,
    start: Coord,
    outward: tuple[int, int],
    z_peak: int,
    z_height_map: ZHeightMap,
    max_scan: int = 64,
) -> tuple[int, int]:
    """Walk ``start`` along ``outward`` until a voxel blocks.

    Returns ``(L, z_end)``. ``L == 0`` if the first cell is already blocked.
    ``z_end`` is the last free cell (``z_peak`` when L=0).
    """
    dx, dy = int(outward[0]), int(outward[1])
    if (dx, dy) == (0, 0) or (abs(dx) + abs(dy) != 1):
        return 0, int(z_peak)
    facing = GRID_DELTA_TO_FACING.get((dx, dy))
    if facing is None:
        return 0, int(z_peak)

    peak = int(z_peak)
    origin = (int(start[0]) - dx, int(start[1]) - dy)
    z_prev = peak
    blocked = False

    def mill_stop(cell: Coord, _k: int) -> bool:
        nonlocal z_prev, blocked
        z = z_height_map(cell)
        if z is None or int(z) >= peak or int(z) >= z_prev:
            blocked = True
            return True
        z_prev = int(z)
        return False

    ray = walk_grid_ray(
        origin, facing, max_k=max(0, int(max_scan)), stop=mill_stop,
    )
    if blocked:
        ray = ray[:-1]
    if not ray:
        return 0, peak
    z_end = z_height_map(ray[-1])
    if z_end is None:
        return 0, peak
    return len(ray), int(z_end)
