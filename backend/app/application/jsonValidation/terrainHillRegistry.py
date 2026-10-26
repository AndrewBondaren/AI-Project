"""One world boundary for landcover wire aliases and registry metadata."""
from __future__ import annotations

from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.db.models.world import World


def apply_landcover_policies(registry: WorldTerrainRegistry,
                            policy: LandcoverRegionsCategoryPolicy, raw) -> WorldTerrainRegistry:
    explicit_hills = registry.authored_hill_keys_from_wire(raw)
    entries = {entry.system_terrain: entry for entry in registry.root}
    for source, override in policy.terrain_policies.items():
        key = override.system_terrain
        entry = entries.get(key)
        if entry is None:
            continue
        source_entry = entries.get(source) or WorldTerrainRegistry.canonical_defaults().entry_for(source)
        entries[key] = override.apply_to(entry, source=source_entry,
                                         registry_hills_authored=key in explicit_hills)
    return WorldTerrainRegistry(list(entries.values()))


def terrain_with_hills(world: World) -> WorldTerrainRegistry:
    from app.application.jsonValidation.worldRow import terrain
    return terrain(world)
