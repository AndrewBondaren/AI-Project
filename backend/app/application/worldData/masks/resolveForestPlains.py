"""Climate → forest / plains / tundra (no mountain). tz_map_light_bake § Surface mask domains."""

from __future__ import annotations

from app.dataModel.climate.enums.climateZone import ClimateZone, ClimateZoneProfile
from app.dataModel.climate.worldClimateScalars import WorldClimateScalars
from app.dataModel.terrainMasks.worldTerrainMasks import (
    ForestsCategoryPolicy,
    PlainsCategoryPolicy,
    WorldTerrainMasks,
)


def _pick(candidates: list[str], terrain_set: set[str], fallback: str) -> str:
    for key in candidates:
        if key in terrain_set:
            return key
    if fallback in terrain_set:
        return fallback
    return next(iter(terrain_set), fallback)


def profile_for_zone_key(system_climate_zone: str | None) -> ClimateZoneProfile:
    key = (system_climate_zone or "").strip().lower()
    if not key:
        key = WorldClimateScalars.canonical_defaults().default_climate_zone
    zone = ClimateZone.from_system_climate(key)
    if zone is not None:
        return zone.to_profile()
    default_key = WorldClimateScalars.canonical_defaults().default_climate_zone
    fallback = ClimateZone.from_system_climate(default_key)
    if fallback is None:
        return ClimateZone.TEMPERATE.to_profile()
    return fallback.to_profile()


def resolve_forest_plains(
    *,
    base_rainfall: int,
    base_temperature: int,
    terrain_set: set[str],
    forests: ForestsCategoryPolicy,
    plains: PlainsCategoryPolicy,
) -> str:
    """Biome only — mountain/ravine/road are other domains."""
    plains_key = plains.system_terrain
    if not terrain_set:
        return plains_key
    if base_rainfall >= forests.forest_min_rainfall:
        return _pick([forests.system_terrain, plains_key], terrain_set, plains_key)
    if base_temperature <= forests.tundra_max_base_temperature:
        return _pick(
            [forests.tundra_system_terrain, plains_key],
            terrain_set,
            plains_key,
        )
    return _pick([plains_key], terrain_set, plains_key)


def resolve_forest_plains_from_zone(
    *,
    system_climate_zone: str | None,
    terrain_set: set[str],
    masks: WorldTerrainMasks | None = None,
) -> str:
    pol = masks or WorldTerrainMasks.canonical_defaults()
    profile = profile_for_zone_key(system_climate_zone)
    return resolve_forest_plains(
        base_rainfall=profile.base_rainfall,
        base_temperature=profile.base_temperature,
        terrain_set=terrain_set,
        forests=pol.default_forests,
        plains=pol.default_plains,
    )
