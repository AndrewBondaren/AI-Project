"""Resolve L0 world_map wire ``system_terrain`` — shared by read fallback and L2 refine.

See docs/tz_world_pack_storage.md § Terrain mask carry (WP-PERF-22-OPEN-1).
"""

from __future__ import annotations

from app.application.jsonValidation import terrain_system_keys
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.worldPack.worldMapCellWire import WorldMapCellWire
from app.db.models.world import World


def default_surface_terrain(world: World) -> str:
    """Plains (or first registry key) when wire has no ``system_terrain``."""
    plains = WorldTerrainMasks.canonical_defaults().default_plains.system_terrain
    registry = WorldTerrainRegistry.canonical_defaults()
    entry = registry.entry_for(plains)
    if entry is not None:
        return entry.system_terrain
    keys = terrain_system_keys(world)
    if plains in keys:
        return plains
    if keys:
        return next(iter(sorted(keys)))
    return registry.root[0].system_terrain


def resolve_world_map_terrain(world: World, cell: WorldMapCellWire | None) -> str:
    """Wire ``system_terrain`` if set; else default plains."""
    if cell is not None and cell.system_terrain:
        return str(cell.system_terrain)
    return default_surface_terrain(world)
