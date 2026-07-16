"""Skeleton column terrain helpers (solid only; no liquid). Surface biome → masks.resolveForestPlains."""

from __future__ import annotations

from app.application.worldData.masks.resolveForestPlains import resolve_forest_plains_from_zone
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks


def _pick(candidates: list[str], terrain_set: set[str]) -> str:
    for t in candidates:
        if t in terrain_set:
            return t
    plains = WorldTerrainMasks.canonical_defaults().default_plains.system_terrain
    return next(iter(terrain_set), plains)


def subsurface_terrain_at_z(terrain_set: set[str]) -> str:
    plains = WorldTerrainMasks.canonical_defaults().default_plains.system_terrain
    return _pick(["earth", plains], terrain_set)


def magma_terrain(terrain_set: set[str]) -> str:
    if "magma" in terrain_set:
        return "magma"
    return subsurface_terrain_at_z(terrain_set)


def surface_biome_terrain(
    terrain_set: set[str],
    *,
    system_climate_zone: str | None = None,
    masks: WorldTerrainMasks | None = None,
) -> str:
    """Outdoor surface biome (forest/plains/tundra) — not mountain/ravine/road."""
    zone = system_climate_zone
    if zone is None:
        zone = WorldClimateScalars.canonical_defaults().default_climate_zone
    return resolve_forest_plains_from_zone(
        system_climate_zone=zone,
        terrain_set=terrain_set,
        masks=masks,
    )
