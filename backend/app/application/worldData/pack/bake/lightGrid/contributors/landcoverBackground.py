"""Transitional default_* background for cells outside region footprints."""

from __future__ import annotations

import logging

from app.application.jsonValidation import terrain, terrain_masks
from app.application.worldData.masks.resolveForestPlains import (
    profile_for_zone_key,
    resolve_forest_plains,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.masks.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.dataModel.climate.enums.climateZone import ClimateZone

logger = logging.getLogger(__name__)


def apply_background(compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
    masks = terrain_masks(ctx.world)
    forests = masks.default_forests
    plains = masks.default_plains
    forests_on = masks.category_enabled(forests)
    plains_on = masks.category_enabled(plains)
    if not forests_on and not plains_on:
        logger.debug(
            "light_contributor_landcover | world=%s skipped=disabled",
            ctx.world.world_uid,
        )
        return
    terrain_set = ctx.terrain_system_keys
    if not terrain_set:
        return
    forest_key = forests.system_terrain
    registry = terrain(ctx.world)
    by_key: dict[str, set[LightCellRef]] = {}
    for gx, gy in ctx.tiles:
        for tx, ty, cell in compose.iter_tile(gx, gy):
            if cell.region_uid is not None:
                continue
            zone = (
                ClimateZone.from_world_map_wire_id(cell.climate_zone_id)
                if cell.climate_zone_id is not None
                else None
            )
            zone_key = zone.system_climate if zone is not None else None
            profile = profile_for_zone_key(zone_key)
            preferred = resolve_forest_plains(
                base_rainfall=profile.base_rainfall,
                base_temperature=profile.base_temperature,
                terrain_set=terrain_set,
                forests=forests,
                plains=plains,
            )
            if preferred == forest_key:
                key = preferred if forests_on else (plains.system_terrain if plains_on else None)
            elif preferred == plains.system_terrain:
                key = plains.system_terrain if plains_on else None
            else:
                key = preferred if plains_on else None
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
