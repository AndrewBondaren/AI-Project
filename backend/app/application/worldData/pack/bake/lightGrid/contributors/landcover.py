"""Landcover contributor — terrain from relief z (tz_map_light_bake)."""

from __future__ import annotations

import logging
from collections import Counter

from app.application.worldData.generators.terrain.terrainZ import surface_terrain_at_z
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose

logger = logging.getLogger(__name__)


class LandcoverContributor:
    name = "landcover"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        terrain_set = ctx.terrain_system_keys
        if not terrain_set:
            logger.debug(
                "light_contributor_landcover | world=%s skipped=empty_terrain_keys",
                ctx.world.world_uid,
            )
            return
        terrain_hist: Counter[str] = Counter()
        cells = 0
        for gx, gy in ctx.tiles:
            for tx, ty, cell in compose.iter_tile(gx, gy):
                cell.system_terrain = surface_terrain_at_z(cell.surface_z, terrain_set)
                terrain_hist[cell.system_terrain or "?"] += 1
                cells += 1
        logger.debug(
            "light_contributor_landcover | world=%s cells=%d terrain_keys=%d terrain_hist=%s",
            ctx.world.world_uid,
            cells,
            len(terrain_set),
            dict(terrain_hist),
        )
