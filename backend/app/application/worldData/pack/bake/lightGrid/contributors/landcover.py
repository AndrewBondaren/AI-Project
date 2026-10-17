"""LANDCOVER runner with transitional per-cell background."""

from app.application.jsonValidation import terrain_masks
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
        masks = terrain_masks(ctx.world)
        if masks.default_landcover is not None and masks.category_enabled(masks.default_landcover):
            run_mask_domain(compose, ctx, LandcoverMaterializer(prepare_landcover_inputs(ctx)), masks)
        elif masks.enabled and masks.declared_regions and masks.default_landcover is None:
            raise ValueError("declared_regions require explicit default_landcover generation parameters")
        apply_background(compose, ctx)
