"""Apply the frozen pre-mountain light base without resampling live inputs."""

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.masks.enums.maskDomainId import LightContributorId


class ReliefContributor:
    name = LightContributorId.RELIEF.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        light = ctx.require_surface_bundle().relief.payload.light
        tiles = set(ctx.tiles)
        for ref, z in light.base_surface_z:
            if (ref.gx, ref.gy) in tiles:
                compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty).surface_z = z
