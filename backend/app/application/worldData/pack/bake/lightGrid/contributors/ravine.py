"""Paint scope-independent frozen ravine effects on requested tiles."""

from app.application.worldData.pack.bake.lightGrid.paintTerrain import paint_system_terrain_cell
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.masks.enums.maskDomainId import LightContributorId


class RavineContributor:
    name = LightContributorId.RAVINE.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        light = ctx.require_surface_bundle().relief.payload.light
        tiles = set(ctx.tiles)
        for effect in light.ravine_cells:
            ref = effect.cell
            if (ref.gx, ref.gy) not in tiles:
                continue
            paint_system_terrain_cell(compose, ref.gx, ref.gy, ref.tx, ref.ty,
                light.ravine_terrain, registry=light.terrain_merge, preserve_hydro=True)
            compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty).surface_z = effect.surface_z
