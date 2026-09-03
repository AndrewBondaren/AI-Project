"""
SCH-WORLD-TERRAIN — `worlds.terrain_*` master data.

N1-W-02 `terrain_registry`, N1-W-03 `terrain_category_registry`, generation scalars.
Эталон: fixtures/world_template.json, docs/tz_locations.md, docs/tz_terrain_generation.md.
"""

from app.dataModel.terrain.relief import ReliefSideKind, ReliefSideSpec
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.terrain.terrainCategoryEntry import TerrainCategoryEntry
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrain.worldTerrainCategoryRegistry import WorldTerrainCategoryRegistry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.worldTerrainScalars import (
    CANONICAL_ELEVATION_LAPSE_RATE,
    CANONICAL_Z_MAX,
    CANONICAL_Z_MIN,
    CHUNK_COLUMNS_MIN,
    SUBSURFACE_DEPTH_MIN,
    TERRAIN_CHUNK_COLUMNS_DEFAULT,
    WorldTerrainScalars,
)

__all__ = [
    "CANONICAL_ELEVATION_LAPSE_RATE",
    "CANONICAL_Z_MAX",
    "CANONICAL_Z_MIN",
    "CHUNK_COLUMNS_MIN",
    "SUBSURFACE_DEPTH_MIN",
    "TERRAIN_CHUNK_COLUMNS_DEFAULT",
    "ReliefSideKind",
    "ReliefSideSpec",
    "SceneVolumePolicy",
    "TerrainCategoryEntry",
    "TerrainRegistryEntry",
    "WorldTerrainCategoryRegistry",
    "WorldTerrainRegistry",
    "WorldTerrainScalars",
]
