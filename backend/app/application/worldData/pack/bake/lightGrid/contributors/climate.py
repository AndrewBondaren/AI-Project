"""Climate contributor — zone id at light-cell center (tz_map_light_bake)."""

from __future__ import annotations

from app.application.worldData.generators.coordinates import meters_to_grid_x, meters_to_grid_y
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import light_cell_center_m
from app.dataModel.climate.enums.climateZone import ClimateZone


def _climate_zone_id(zone_key: str) -> int | None:
    zone = ClimateZone.from_system_climate(zone_key)
    if zone is None:
        return None
    for idx, member in enumerate(ClimateZone):
        if member is zone:
            return idx
    return None


class ClimateContributor:
    name = "climate"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        pole = ctx.pole_field
        if pole is None and ctx.surface_planning is not None:
            pole = ctx.surface_planning.pole_field
        if pole is None:
            return

        world = ctx.world
        scale = compose.scale
        tile_m = scale.tile_m
        for gx, gy in ctx.tiles:
            for ty in range(scale.side):
                for tx in range(scale.side):
                    xm, ym = light_cell_center_m(gx, gy, tx, ty, scale)
                    mgx = int(meters_to_grid_x(xm, tile_m))
                    mgy = int(meters_to_grid_y(ym, tile_m))
                    sample = pole.sample(world, mgx, mgy)
                    compose.ensure(gx, gy, tx, ty).climate_zone_id = _climate_zone_id(
                        sample.system_climate_zone,
                    )
