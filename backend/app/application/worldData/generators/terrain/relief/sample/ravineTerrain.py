"""Ravine mask ``system_terrain`` from world masks."""

from __future__ import annotations

from app.application.jsonValidation import terrain_masks
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.db.models.world import World


def ravine_terrain_key(world: World | None = None) -> str:
    """Depression ``system_terrain`` from ``WorldTerrainMasks`` (not a string literal)."""
    masks = (
        terrain_masks(world)
        if world is not None
        else WorldTerrainMasks.canonical_defaults()
    )
    return str(masks.default_ravines.system_terrain)
