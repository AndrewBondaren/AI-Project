"""Shared coverage scorer for cells outside region footprints."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain, terrain_masks
from app.application.worldData.regions.coverageBackground import background_key_for_zone
from app.application.worldData.generators.climate.registry import profile_for
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.maskDomains.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.dataModel.registryKey import RegistryKey
from app.dataModel.climate.climateZone.worldClimateZoneRegistry import WorldClimateZoneRegistry
from app.dataModel.climate.enums.climateZone import ClimateZone

logger = logging.getLogger(__name__)


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
            zone = ClimateZone.from_world_map_wire_id(cell.climate_zone_id) if cell.climate_zone_id is not None else None
            profile = (ctx.working.climate.profile_for_key(RegistryKey[WorldClimateZoneRegistry](zone.system_climate)) if ctx.working is not None
                       else profile_for(ctx.world, zone.system_climate)) if zone is not None else None
            key = background_key_for_zone(cell.climate_zone_id, masks, terrain_set, registry, profile=profile)
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
