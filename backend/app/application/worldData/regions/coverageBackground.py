"""Shared scorer for surface context; missing climate uses the authored background."""

from app.application.worldData.regions.coverageResolver import resolve
from app.application.worldData.regions.regionFacts import ClimateFacts, RegionFacts
from app.dataModel.climate.enums.climateZone import ClimateZone, ClimateZoneProfile
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy


def coverage_registry(registry: WorldTerrainRegistry, policy: LandcoverRegionsCategoryPolicy,
                      *, autoresolve: bool = False) -> WorldTerrainRegistry:
    disabled = {p.system_terrain for p in policy.terrain_policies.values() if not p.enabled}
    if autoresolve:
        disabled.update(p.system_terrain for p in policy.terrain_policies.values() if not p.autoresolve)
    disabled.update(source for source, p in policy.terrain_policies.items() if source != p.system_terrain)
    return WorldTerrainRegistry([e for e in registry.root if e.system_terrain not in disabled
                                 and e.eligibility])


def surface_coverage(*, registry: WorldTerrainRegistry, policy: LandcoverRegionsCategoryPolicy,
                     system_climate_zone: str | None = None,
                     profile: ClimateZoneProfile | None = None) -> str | None:
    if not policy.enabled:
        return None
    fallback_allowed = (registry.entry_for(policy.fallback_terrain) is not None and
        all(p.enabled for p in policy.terrain_policies.values()
            if p.system_terrain == policy.fallback_terrain))
    if profile is None and system_climate_zone is not None:
        zone = ClimateZone.from_system_climate(system_climate_zone)
        profile = zone.to_profile() if zone is not None else None
    if profile is None:
        return policy.fallback_terrain if fallback_allowed else None
    facts = RegionFacts(climate=ClimateFacts(rainfall_mean=profile.base_rainfall,
                                           temperature=profile.base_temperature))
    candidates = coverage_registry(registry, policy)
    result = resolve(facts, candidates) if candidates.root else None
    return result.target_key if result else (
        policy.fallback_terrain if fallback_allowed else None)
