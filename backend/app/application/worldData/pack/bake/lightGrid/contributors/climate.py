"""Climate contributor — zone id at light-cell center (tz_map_light_bake)."""

from __future__ import annotations

import logging
from collections import Counter

from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.application.worldData.generators.coordinates import fine_to_grid_x, fine_to_grid_y
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_cell_center_fine
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.masks.enums.maskDomainId import LightContributorId

logger = logging.getLogger(__name__)


def _climate_zone_id(zone_key: str) -> int | None:
    zone = ClimateZone.from_system_climate(zone_key)
    if zone is None:
        return None
    return zone.world_map_wire_id()


class ClimateContributor:
    name = LightContributorId.CLIMATE.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        ctx.require_surface_bundle()
        climate = ctx.require_working().climate
        world = ctx.world
        scale = compose.scale
        tile_macro = scale.tile_macro
        zone_hist: Counter[str] = Counter()
        cells = 0
        for gx, gy in ctx.tiles:
            for ty in range(scale.side):
                for tx in range(scale.side):
                    xm, ym = light_cell_center_fine(gx, gy, tx, ty, scale)
                    mgx = int(fine_to_grid_x(xm, tile_macro))
                    mgy = int(fine_to_grid_y(ym, tile_macro))
                    sample = climate.sample_pole(GridX(mgx), GridY(mgy))
                    zone_id = _climate_zone_id(sample.system_climate_zone)
                    compose.ensure(gx, gy, tx, ty).climate_zone_id = zone_id
                    zone_hist[str(zone_id if zone_id is not None else sample.system_climate_zone)] += 1
                    cells += 1
        logger.debug(
            "light_contributor_climate | world=%s cells=%d zone_hist=%s",
            world.world_uid,
            cells,
            dict(zone_hist),
        )
