"""Shared ortho deltas + landward seed skips for ribbon samples (Wave D polish)."""

from __future__ import annotations

from collections.abc import Iterator

from app.application.worldData.masks.terrainMerge import PRESERVE_HYDROLOGY_ROLES
from app.application.worldData.pack.bake.lightGrid.cell import LightGridCell
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing

# Stable cardinal order (E,W,N,S) — Facing SoT (RELIEF-T-62).
CARDINAL_ORTHO_DELTAS: tuple[tuple[int, int], ...] = tuple(
    CARDINAL_WALL_OUTWARD_DELTA[f]
    for f in (Facing.EAST, Facing.WEST, Facing.NORTH, Facing.SOUTH)
)

Coord = tuple[int, int]


def iter_compose_cells(
    compose: LightGridCompose,
    tile_set: set[Coord],
) -> Iterator[tuple[Coord, LightGridCell]]:
    """Yield ``((lx, ly), cell)`` for ensured cells in ``tile_set``."""
    side = compose.scale.side
    for gx, gy in sorted(tile_set):
        for ty in range(side):
            for tx in range(side):
                cell = compose.get(gx, gy, tx, ty)
                if cell is None:
                    continue
                yield (gx * side + tx, gy * side + ty), cell


def landward_seed_blocked(
    cell: LightGridCell,
    *,
    road_key: str,
) -> bool:
    """True if cell must not be a ribbon seed (road / graded / pin / open water)."""
    if not cell.system_terrain:
        return True
    if cell.system_terrain == road_key:
        return True
    if cell.system_grade_uid:
        return True
    if cell.location_pin is not None:
        return True
    if cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
        return True
    return False
