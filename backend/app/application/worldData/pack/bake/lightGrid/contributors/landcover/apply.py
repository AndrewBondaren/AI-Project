"""Region competition uses the common precedence rule and common terrain writer."""

from app.application.worldData.generators.terrain.landcover.types import (
    LandcoverCollectContext,
    RegionSource,
    ResolvedRegion,
)
from app.application.jsonValidation import terrain
from app.application.worldData.generators.terrain.landcover.materializer import LandcoverMaterializer
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.application.worldData.pack.bake.lightGrid.maskDomains.applyFootprint import apply_terrain_footprint
from app.application.worldData.masks.footprint import LightCellRef, MaskFootprint
from app.application.worldData.masks.regionPrecedence import RegionCandidate
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


class LandcoverLightAdapter:
    """Bind the pack scope and own L0 canvas competition for a domain materializer."""

    domain = LandcoverMaterializer.domain

    def __init__(self, materializer: LandcoverMaterializer) -> None:
        self.materializer = materializer
        self.winners: dict[LightCellRef, RegionCandidate] = {}

    def begin_pass(self) -> None:
        self.winners.clear()
        self.materializer.begin_pass()

    def category_policy(self, masks: WorldTerrainMasks) -> MaskCategoryPolicy:
        return self.materializer.category_policy(masks)

    def collect(self, ctx: LightGridBakeContext, policy: MaskCategoryPolicy) -> list[ResolvedRegion]:
        scope = LandcoverCollectContext(ctx.world, tuple(ctx.locations), ctx.scale, tuple(ctx.tiles))
        return self.materializer.collect(scope, policy)

    def materialize(self, spec: ResolvedRegion, scale: LightGridScale) -> MaskFootprint:
        return self.materializer.materialize(spec, scale)

    def apply(self, compose: LightGridCompose, footprint: MaskFootprint, spec: ResolvedRegion,
              masks: WorldTerrainMasks, *, tile_set: set[tuple[int, int]], ctx: LightGridBakeContext) -> None:
        apply_region(compose, footprint, spec, terrain(ctx.world), self.winners, tile_set)


def apply_region(compose: LightGridCompose, footprint: MaskFootprint, region: ResolvedRegion,
                 registry: WorldTerrainRegistry, winners: dict[LightCellRef, RegionCandidate],
                 tile_set: set[tuple[int, int]]) -> None:
    candidate = RegionCandidate(
        region.current_type, region.spec, region.region_uid, region.claim_area,
        declared=region.source != RegionSource.AUTORESOLVE,
    )
    apply_terrain_footprint(compose, footprint,
                            system_terrain=region.current_type, registry=registry,
                            tile_set=tile_set, preserve_hydro=True, region=candidate, winners=winners)
