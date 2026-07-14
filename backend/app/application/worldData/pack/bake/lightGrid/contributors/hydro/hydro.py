"""Hydro contributor — thin facade over declared + coarse open-water steps."""

from __future__ import annotations

import logging

from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.load.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.coarseOpenWater import (
    apply_coarse_open_water,
)
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.declaredBasins import (
    apply_declared_basins,
)
from app.application.worldData.pack.bake.lightGrid.contributors.hydro.declaredRivers import (
    apply_declared_rivers,
)

logger = logging.getLogger(__name__)


class HydroContributor:
    name = "hydro"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        world_uid = ctx.world.world_uid
        if not is_hydrology_enabled(ctx.world):
            logger.debug(
                "light_contributor_hydro | world=%s skipped=disabled",
                world_uid,
            )
            return
        declared = load_declared_hydrology(ctx.world, ctx.locations)
        # Order: corridors → basins/coast → coarse SEA/LAKE (skip existing RIVER).
        rivers = apply_declared_rivers(compose, ctx, declared)
        basins = apply_declared_basins(compose, ctx, declared)
        coarse = apply_coarse_open_water(compose, ctx)
        logger.debug(
            "light_contributor_hydro | world=%s rivers=%s basins=%s coarse=%s",
            world_uid,
            rivers,
            basins,
            coarse,
        )
