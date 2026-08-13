"""Open-land terrain keys from world masks — R36u-T-5."""

from __future__ import annotations

from app.application.jsonValidation import terrain_masks
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.db.models.world import World


def open_land_terrain_keys(world: World | None = None) -> frozenset[str]:
    """Plains + forest ``system_terrain`` from ``WorldTerrainMasks`` (not string literals)."""
    masks = (
        terrain_masks(world)
        if world is not None
        else WorldTerrainMasks.canonical_defaults()
    )
    return frozenset({
        masks.default_plains.system_terrain,
        masks.default_forests.system_terrain,
    })
