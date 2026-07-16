"""Landcover contributor — forest/plains/tundra from climate (tz_map_light_bake)."""

from __future__ import annotations

import logging
from collections import Counter

from app.application.jsonValidation import terrain_masks
from app.application.worldData.pack.bake.lightGrid.paintTerrain import paint_system_terrain_cell
from app.application.worldData.masks.resolveForestPlains import (
    profile_for_zone_key,
    resolve_forest_plains,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.climate.enums.climateZone import ClimateZone

logger = logging.getLogger(__name__)


class LandcoverContributor:
    name = "landcover"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
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
        forest_keys = {forests.system_terrain, forests.tundra_system_terrain}
        terrain_hist: Counter[str] = Counter()
        cells = 0
        for gx, gy in ctx.tiles:
            for tx, ty, cell in compose.iter_tile(gx, gy):
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
                if preferred in forest_keys:
                    key = preferred if forests_on else (plains.system_terrain if plains_on else None)
                elif preferred == plains.system_terrain:
                    key = plains.system_terrain if plains_on else None
                else:
                    key = preferred if plains_on else None
                if key is None:
                    continue
                if paint_system_terrain_cell(
                    compose, gx, gy, tx, ty, key, masks=masks, preserve_hydro=False,
                ):
                    terrain_hist[key] += 1
                    cells += 1
        logger.debug(
            "light_contributor_landcover | world=%s cells=%d terrain_hist=%s",
            ctx.world.world_uid,
            cells,
            dict(terrain_hist),
        )
