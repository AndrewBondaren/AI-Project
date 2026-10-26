"""Paint ``system_terrain`` on light cells — shared by mountain/ravine/road/landcover."""

from __future__ import annotations

from app.application.worldData.masks.terrainMerge import (
    PRESERVE_HYDROLOGY_ROLES,
    may_paint_terrain,
)
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import TerrainMergeEntry


def paint_system_terrain(
    compose: LightGridCompose,
    light_cells: set[tuple[int, int]],
    system_terrain: str,
    *,
    registry: WorldTerrainRegistry | tuple[TerrainMergeEntry, ...],
    tile_set: set[tuple[int, int]],
    preserve_hydro: bool = True,
) -> int:
    """Apply terrain with merge rank; skip SEA/LAKE/RIVER when ``preserve_hydro``."""
    scale = compose.scale
    painted = 0
    for lx, ly in light_cells:
        gx = lx // scale.side
        gy = ly // scale.side
        tx = lx % scale.side
        ty = ly % scale.side
        if (gx, gy) not in tile_set:
            continue
        if not (0 <= tx < scale.side and 0 <= ty < scale.side):
            continue
        cell = compose.ensure(gx, gy, tx, ty)
        if preserve_hydro and cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
            continue
        if not may_paint_terrain(cell.system_terrain, system_terrain, registry):
            continue
        cell.system_terrain = system_terrain
        cell.region_uid = None
        painted += 1
    return painted


def paint_system_terrain_cell(
    compose: LightGridCompose,
    gx: int,
    gy: int,
    tx: int,
    ty: int,
    system_terrain: str,
    *,
    registry: WorldTerrainRegistry | tuple[TerrainMergeEntry, ...],
    preserve_hydro: bool = True,
) -> bool:
    cell = compose.ensure(gx, gy, tx, ty)
    if preserve_hydro and cell.hydrology_role in PRESERVE_HYDROLOGY_ROLES:
        return False
    if not may_paint_terrain(cell.system_terrain, system_terrain, registry):
        return False
    cell.system_terrain = system_terrain
    cell.region_uid = None
    return True
