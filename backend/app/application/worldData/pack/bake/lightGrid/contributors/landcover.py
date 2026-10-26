"""Unified LANDCOVER runner and per-cell background."""

from app.application.jsonValidation import terrain_masks, terrain
from app.application.worldData.pack.bake.wildernessRegionIndex import build_region_index
from app.application.worldData.generators.terrain.landcover.materializer import LandcoverMaterializer
from app.application.worldData.masks.runMaskDomain import run_mask_domain
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.landcoverBackground import apply_background
from app.application.worldData.pack.bake.lightGrid.contributors.landcoverInputs import prepare_landcover_inputs
from app.dataModel.masks.enums.maskDomainId import LightContributorId


class LandcoverContributor:
    name = LightContributorId.LANDCOVER.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        ctx.wilderness_region_entries.clear()
        masks = terrain_masks(ctx.world)
        if masks.category_enabled(masks.default_landcover) and (
            masks.declared_regions or masks.default_landcover.autoresolve
        ):
            materializer = LandcoverMaterializer(prepare_landcover_inputs(ctx))
            run_mask_domain(compose, ctx, materializer, masks)
            ctx.wilderness_region_entries = build_region_index(materializer.resolved_regions, ctx.scale, registry=terrain(ctx.world))
        apply_background(compose, ctx)
