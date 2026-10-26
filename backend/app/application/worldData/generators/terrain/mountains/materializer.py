"""L0 mountain consumer: stamped layout identity and frozen absolute light effects."""

from app.application.worldData.generators.terrain.mountains.formPipeline import materialize_mountain_entry
from app.application.worldData.masks.footprint import MaskFootprint
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.bake.lightGrid.paintTerrain import paint_system_terrain_cell
from app.dataModel.masks.enums.maskDomainId import MaskDomainId
from app.dataModel.terrainMasks.mountain.specs import MountainDeclareEntry


class MountainMaskMaterializer:
    domain = MaskDomainId.MOUNTAINS

    def collect(self, ctx: LightGridBakeContext) -> tuple[MountainDeclareEntry, ...]:
        return ctx.require_surface_bundle().relief.payload.mountain_layout.entries

    def materialize(self, spec: MountainDeclareEntry, scale: LightGridScale) -> MaskFootprint:
        return materialize_mountain_entry(spec, scale)

    def apply_plan(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        relief = ctx.require_surface_bundle().relief.payload
        tiles = set(ctx.tiles)
        for effect in relief.light.mountain_cells:
            ref = effect.cell
            if (ref.gx, ref.gy) not in tiles:
                continue
            paint_system_terrain_cell(compose, ref.gx, ref.gy, ref.tx, ref.ty,
                relief.mountain_layout.terrain_key, registry=relief.light.terrain_merge,
                preserve_hydro=True)
            cell = compose.ensure(ref.gx, ref.gy, ref.tx, ref.ty)
            cell.surface_z = effect.surface_z
            if effect.facing is not None:
                cell.system_facing = effect.facing
