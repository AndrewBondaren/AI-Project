"""Resolve transitional builtin hill policies at the world wire boundary."""
from __future__ import annotations

from app.application.jsonValidation.worldRow import terrain, terrain_masks
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.db.models.world import World


def terrain_with_hills(world: World) -> WorldTerrainRegistry:
    """Explicit registry hills (including null) win over legacy world knobs."""
    registry = terrain(world)
    raw = world.terrain_registry
    explicit = {
        row["system_terrain"] for row in raw
        if isinstance(row, dict) and "system_terrain" in row and "hills" in row
    } if isinstance(raw, list) else set()
    masks = terrain_masks(world)
    legacy = {
        WorldTerrainRegistry.plains_terrain_key(): masks.default_plains.hills,
        WorldTerrainRegistry.forest_terrain_key(): masks.default_forests.hills,
    }
    return WorldTerrainRegistry([
        entry.model_copy(update={"hills": legacy[entry.system_terrain]})
        if entry.system_terrain in legacy and entry.system_terrain not in explicit
        else entry
        for entry in registry.root
    ])
