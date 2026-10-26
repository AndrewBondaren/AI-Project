"""Unified LANDCOVER plugin."""

from app.application.jsonValidation import terrain, terrain_masks
from app.application.worldData.generators.terrain.landcover.autoresolve.claim import autoresolve_regions
from app.application.worldData.generators.terrain.landcover.collect import resolve_collected
from app.application.worldData.generators.terrain.landcover.regionIdentityCheck import require_unique_region_uids
from app.application.worldData.generators.terrain.landcover.types import LandcoverCollectContext, LandcoverInputs, RegionSource, ResolvedRegion
from app.application.worldData.masks.footprint import MaskFootprint
from app.application.worldData.masks.regionIdentity import declared_region_identity
from app.application.worldData.masks.regionRasterContext import (
    RasterWorld, RegionClaim, RegionRasterContext,
)
from app.application.worldData.masks.regionRasterizer import (
    ClaimOwnersIndex, rasterize_claim_light, rasterize_light,
)
from app.application.worldData.masks.collection.defaultCollect import default_collect
from app.application.worldData.regions.coverageBackground import coverage_registry
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.registryKey import RegistryKey
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.masks.enums.maskDomainId import MaskDomainId
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.dataModel.terrainMasks.landcoverRegionsCategoryPolicy import LandcoverRegionsCategoryPolicy
from app.dataModel.terrainMasks.worldTerrainMasks import WorldTerrainMasks
from app.ids.regionIdentity import region_uid
from app.ids import seed_root


class LandcoverMaterializer:
    domain = MaskDomainId.LANDCOVER

    def __init__(self, inputs: LandcoverInputs) -> None:
        self.inputs = inputs
        self.resolved_regions: list[ResolvedRegion] = []
        self._claim_indexes: dict[RegionClaim, ClaimOwnersIndex] = {}

    def begin_pass(self) -> None:
        self.resolved_regions.clear()
        self._claim_indexes.clear()

    def category_policy(self, masks: WorldTerrainMasks) -> LandcoverRegionsCategoryPolicy:
        return masks.default_landcover

    def load_declared(self, ctx: LandcoverCollectContext) -> list[ResolvedRegion]:
        return [ResolvedRegion(ctx.world.world_uid, declared_region_identity(ctx.world.world_uid, spec).region_uid,
                                spec, RegistryKey[WorldTerrainRegistry](spec.entry_type), RegionSource.DECLARED, self.inputs.topology, entry_type=RegistryKey[WorldTerrainRegistry](spec.entry_type))
                for spec in terrain_masks(ctx.world).declared_regions]

    def load_anchor_specs(self, ctx: LandcoverCollectContext) -> list[ResolvedRegion]:
        return [ResolvedRegion(ctx.world.world_uid, region_uid(ctx.world.world_uid, anchor_uid=anchor.anchor_uid),
                                anchor.spec, RegistryKey[WorldTerrainRegistry](anchor.spec.entry_type), RegionSource.ANCHOR, self.inputs.topology, entry_type=RegistryKey[WorldTerrainRegistry](anchor.spec.entry_type))
                for anchor in self.inputs.anchor_specs]

    def autoresolve_specs(self, ctx: LandcoverCollectContext, policy: MaskCategoryPolicy) -> list[ResolvedRegion]:
        if not isinstance(policy, LandcoverRegionsCategoryPolicy):
            raise TypeError("landcover expects LandcoverRegionsCategoryPolicy")
        regions, index = autoresolve_regions(
            ctx.world.world_uid, seed_root(ctx.world), ctx.scale.tile_macro,
            self.inputs, policy, coverage_registry(terrain(ctx.world), policy, autoresolve=True))
        # The same owners map serves claim_area and every sibling materialize.
        self._claim_indexes[index.claim] = index
        return regions

    def claim_index(self, claim: RegionClaim, world: RasterWorld,
                    raster_ctx: RegionRasterContext) -> ClaimOwnersIndex:
        """Owners map per claim, shared by all sibling regions in this pass."""
        index = self._claim_indexes.get(claim)
        if index is None:
            index = ClaimOwnersIndex(claim, seed_root(world), raster_ctx.fine_topology())
            self._claim_indexes[claim] = index
        return index

    def collect(self, ctx: LandcoverCollectContext, policy: MaskCategoryPolicy) -> list[ResolvedRegion]:
        regions = default_collect(
            self, ctx, policy,
            key=lambda region: ((region.source, tuple(s.seed_xy for s in region.sublocations)) if region.source == RegionSource.AUTORESOLVE
                                else region.spec.identity_key()),
        )
        require_unique_region_uids(regions)
        self.resolved_regions = resolve_collected(regions, ctx, self.inputs, terrain(ctx.world))
        return self.resolved_regions

    def materialize(self, spec: ResolvedRegion, scale: LightGridScale) -> MaskFootprint:
        raster_context = RegionRasterContext(spec.region_uid, spec.spec, scale, spec.topology)
        cells = (rasterize_claim_light(self.claim_index(spec.claim, spec, raster_context), spec, raster_context)
                 if spec.claim is not None
                 else rasterize_light(spec.spec.shape, spec, raster_context))
        return MaskFootprint(cells)
