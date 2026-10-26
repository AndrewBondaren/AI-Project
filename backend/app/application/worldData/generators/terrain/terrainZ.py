"""Skeleton column terrain helpers; coverage uses the shared scorer."""

from __future__ import annotations

import logging

from app.application.worldData.regions.coverageBackground import surface_coverage
from app.application.jsonValidation.terrainHillRegistry import apply_landcover_policies
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.enums.terrainFillRole import TerrainFillRole
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks


logger = logging.getLogger(__name__)


def _column_terrain(role: TerrainFillRole, terrain_set: set[str],
                    registry: WorldTerrainRegistry | None) -> str:
    resolved = registry if registry is not None else WorldTerrainRegistry.canonical_defaults()
    try:
        return resolved.column_terrain_key(role, terrain_set)
    except ValueError:
        logger.warning("terrain | column_fill_unresolved | WarningError | role=%s available=%s",
                       role, sorted(terrain_set))
        raise


def subsurface_terrain_at_z(terrain_set: set[str], *,
                           registry: WorldTerrainRegistry | None = None) -> str:
    return _column_terrain(TerrainFillRole.SUBSURFACE, terrain_set, registry)


def magma_terrain(terrain_set: set[str], *, registry: WorldTerrainRegistry | None = None) -> str:
    return _column_terrain(TerrainFillRole.MAGMA, terrain_set, registry)


def surface_biome_terrain(
    terrain_set: set[str],
    *,
    system_climate_zone: str | None = None,
    masks: WorldTerrainMasks | None = None,
    terrain_registry: WorldTerrainRegistry | None = None,
    climate_profile: ClimateZoneProfile | None = None,
) -> str:
    """Outdoor surface landcover (forest/plains) — not mountain/ravine/road; not biome keys."""
    zone = system_climate_zone
    if zone is None:
        zone = WorldClimateScalars.canonical_defaults().default_climate_zone
    policy = (masks or WorldTerrainMasks.canonical_defaults()).default_landcover
    registry = (terrain_registry if terrain_registry is not None else
                apply_landcover_policies(WorldTerrainRegistry.canonical_defaults(), policy, None))
    registry = WorldTerrainRegistry([entry for entry in registry.root if entry.system_terrain in terrain_set])
    return surface_coverage(registry=registry, policy=policy, system_climate_zone=zone,
                            profile=climate_profile) or policy.fallback_terrain
