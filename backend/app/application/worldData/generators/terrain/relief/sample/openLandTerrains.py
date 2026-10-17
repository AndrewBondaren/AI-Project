"""Open-land grade admission from terrain registry, independently of hills."""
from __future__ import annotations

from app.application.jsonValidation import terrain
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.db.models.world import World


def open_land_terrain_keys(world: World | None = None) -> frozenset[str]:
    registry = terrain(world) if world is not None else WorldTerrainRegistry.canonical_defaults()
    return frozenset(e.system_terrain for e in registry.root if e.supports_open_land_grade)
