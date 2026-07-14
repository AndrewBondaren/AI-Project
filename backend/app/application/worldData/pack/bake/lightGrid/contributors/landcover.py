"""Landcover contributor — terrain from relief z (tz_map_light_bake)."""

from __future__ import annotations

from app.application.worldData.generators.terrain.terrainZ import surface_terrain_at_z
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose


class LandcoverContributor:
    name = "landcover"

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        terrain_set = ctx.terrain_system_keys
        if not terrain_set:
            return
        for gx, gy in ctx.tiles:
            for tx, ty, cell in compose.iter_tile(gx, gy):
                cell.system_terrain = surface_terrain_at_z(cell.surface_z, terrain_set)
