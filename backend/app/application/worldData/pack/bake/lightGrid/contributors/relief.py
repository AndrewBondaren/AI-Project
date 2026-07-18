"""Relief contributor — per-(tx,ty) surface_z (tz_map_light_bake)."""

from __future__ import annotations

import logging
from collections import Counter

from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.coordinates import meters_to_grid_x, meters_to_grid_y
from app.application.worldData.generators.terrain.noise import cell_z_noise
from app.application.worldData.generators.terrain.worldMapSettings import world_z_max, world_z_min
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_cell_center_m
from app.dataModel.masks.enums.maskDomainId import LightContributorId

logger = logging.getLogger(__name__)


class ReliefContributor:
    name = LightContributorId.RELIEF.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        world = ctx.world
        pole = ctx.pole_field
        if pole is None and ctx.surface_planning is not None:
            pole = ctx.surface_planning.pole_field
        if pole is None:
            logger.debug(
                "light_contributor_relief | world=%s skipped=no_pole tiles=%d",
                world.world_uid,
                len(ctx.tiles),
            )
            return

        scale = compose.scale
        tile_m = scale.tile_m
        z_min = world_z_min(world)
        z_max = world_z_max(world)
        seed = world_seed(world)
        # Pre-1.4 relief base — mountain/ravine contributors apply rise/drop once on light.
        planning_z = (
            ctx.surface_planning.coarse_relief_z if ctx.surface_planning is not None else {}
        )
        z_hist: Counter[int] = Counter()
        cells = 0

        for gx, gy in ctx.tiles:
            compose.ensure_tile(gx, gy)
            for ty in range(scale.side):
                for tx in range(scale.side):
                    xm, ym = light_cell_center_m(gx, gy, tx, ty, scale)
                    mgx = int(meters_to_grid_x(xm, tile_m))
                    mgy = int(meters_to_grid_y(ym, tile_m))
                    sample = pole.sample(world, mgx, mgy)
                    base = planning_z.get((mgx, mgy), sample.typical_elevation_z)
                    z = cell_z_noise(seed, xm, ym, int(base), amplitude=1)
                    z = max(z_min, min(z_max, z))
                    compose.ensure(gx, gy, tx, ty).surface_z = z
                    z_hist[z] += 1
                    cells += 1

        logger.debug(
            "light_contributor_relief | world=%s cells=%d tiles=%d planning_z_keys=%d z_hist=%s",
            world.world_uid,
            cells,
            len(ctx.tiles),
            len(planning_z),
            dict(z_hist),
        )
