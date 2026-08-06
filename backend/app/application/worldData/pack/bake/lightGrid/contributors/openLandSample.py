"""Sample open_land Δz sites — Wave D1.

Uphill land cell = abutment (``ref``); downhill ortho neighbor = seed.
Terrains: ``ReliefConditionTerrain`` plains/forest (R34 1:1 with system_terrain).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.shoulderWidth import relief_dz
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.ribbonSampleUtil import (
    CARDINAL_ORTHO_DELTAS,
    iter_compose_cells,
    landward_seed_blocked,
)
from app.dataModel.terrain.relief.enums import ReliefConditionTerrain

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
    samples: list[tuple[tuple[int, int], str, int]] = []
    ref_cells: set[tuple[int, int]] = set()
    seen_seeds: set[tuple[int, int]] = set()

    land: dict[tuple[int, int], tuple[str, int]] = {}
    for xy, cell in iter_compose_cells(compose, tile_set):
        if cell.system_terrain not in _OPEN_LAND_TERRAINS:
            continue
        if landward_seed_blocked(cell, road_key=road_key):
            continue
        land[xy] = (str(cell.system_terrain), int(cell.surface_z))

    for (lx, ly), (_terrain_hi, z_hi) in sorted(land.items()):
        for dx, dy in CARDINAL_ORTHO_DELTAS:
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
