"""Sample open_land Δz sites — Wave D1.

Uphill land cell = abutment (``ref``); downhill ortho neighbor = seed.
Terrains: ``ReliefConditionTerrain`` plains/forest (R34 1:1 with system_terrain).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.shoulderWidth import relief_dz
from app.application.worldData.masks.terrainMerge import PRESERVE_HYDROLOGY_ROLES
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain

_ORTHO = tuple(
    CARDINAL_WALL_OUTWARD_DELTA[f]
    for f in (Facing.EAST, Facing.WEST, Facing.NORTH, Facing.SOUTH)
)

_OPEN_LAND_TERRAINS = frozenset({
    ReliefConditionTerrain.PLAINS.value,
    ReliefConditionTerrain.FOREST.value,
})


def sample_open_land_cells(
    compose: LightGridCompose,
    *,
    tile_set: set[tuple[int, int]],
    road_key: str,
) -> tuple[list[tuple[tuple[int, int], str, int]], set[tuple[int, int]]]:
    """Return (samples, ref_cells). samples sorted by seed xy."""
    scale = compose.scale
    side = scale.side
    samples: list[tuple[tuple[int, int], str, int]] = []
    ref_cells: set[tuple[int, int]] = set()
    seen_seeds: set[tuple[int, int]] = set()

    land: dict[tuple[int, int], tuple[str, int]] = {}
    for gx, gy in sorted(tile_set):
        for ty in range(side):
            for tx in range(side):
                cell = compose.get(gx, gy, tx, ty)
                if cell is None or not cell.system_terrain:
                    continue
                if cell.system_terrain not in _OPEN_LAND_TERRAINS:
                    continue
                if cell.system_terrain == road_key:
                    continue
                if cell.system_grade_uid:
                    continue
                if cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
                    continue
                if cell.location_pin is not None:
                    continue
                lx = gx * side + tx
                ly = gy * side + ty
                land[(lx, ly)] = (str(cell.system_terrain), int(cell.surface_z))

    for (lx, ly), (terrain_hi, z_hi) in sorted(land.items()):
        for dx, dy in _ORTHO:
            seed = (lx + dx, ly + dy)
            low = land.get(seed)
            if low is None:
                continue
            terrain_lo, z_lo = low
            if z_hi <= z_lo:
                continue
            if seed in seen_seeds:
                continue
            seen_seeds.add(seed)
            ref_cells.add((lx, ly))
            samples.append((seed, terrain_lo, relief_dz(z_hi, z_lo)))

    samples.sort(key=lambda item: item[0])
    return samples, ref_cells
