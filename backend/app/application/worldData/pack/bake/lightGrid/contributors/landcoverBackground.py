"""Shared coverage scorer for cells outside region footprints."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain, terrain_masks
from app.application.worldData.regions.coverageBackground import surface_coverage
from app.application.worldData.generators.climate.registry import profile_for
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry

logger = logging.getLogger(__name__)


def background_key_for_zone(
    climate_zone_id: int | None,
    masks: WorldTerrainMasks,
    terrain_set: set[str],
    registry: WorldTerrainRegistry | None = None,
    *, world=None,
) -> str | None:
    """Per-cell landcover fallback key; ``None`` — no background paint."""
    if not masks.category_enabled(masks.default_landcover):
        return None
    if not terrain_set:
        return None
    zone = (
        ClimateZone.from_world_map_wire_id(climate_zone_id)
        if climate_zone_id is not None
        else None
    )
    registry = registry or WorldTerrainRegistry.canonical_defaults()
    registry = WorldTerrainRegistry([e for e in registry.root if e.system_terrain in terrain_set])
    return surface_coverage(registry=registry, policy=masks.default_landcover,
                            system_climate_zone=zone.system_climate if zone else None,
                            profile=profile_for(world, zone.system_climate) if world is not None and zone else None)


def apply_background(compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
    masks = terrain_masks(ctx.world)
    if not masks.category_enabled(masks.default_landcover):
        logger.debug(
            "light_contributor_landcover | world=%s skipped=disabled",
            ctx.world.world_uid,
        )
        return
    terrain_set = ctx.terrain_system_keys
    if not terrain_set:
        return
    registry = terrain(ctx.world)
    by_key: dict[str, set[LightCellRef]] = {}
    for gx, gy in ctx.tiles:
        for tx, ty, cell in compose.iter_tile(gx, gy):
            if cell.region_uid is not None:
                continue
            key = background_key_for_zone(cell.climate_zone_id, masks, terrain_set, registry, world=ctx.world)
            if key is None:
                continue
            by_key.setdefault(key, set()).add(LightCellRef(gx, gy, tx, ty))
    for key, refs in by_key.items():
        painted = apply_terrain_footprint(
            compose, MaskFootprint(frozenset(refs)), system_terrain=key,
            registry=registry, tile_set=set(ctx.tiles), preserve_hydro=True,
        )
        logger.debug("landcover | paint_key_source | region_uid=None source=fallback key=%s cells=%d",
                     key, painted)
