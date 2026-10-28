"""Positive surface landcover contracts; checked statically by Pyright."""

from typing import assert_type

from app.application.worldData.generators.terrain.landcover.materializer import LandcoverMaterializer
from app.application.worldData.generators.terrain.landcover.types import LandcoverCollectContext, ResolvedRegion
from app.application.worldData.masks.collection.defaultCollect import MaskSourceCollector, default_collect
from app.application.worldData.pack.bake.lightGrid.contributors.landcover.apply import LandcoverLightAdapter
from app.application.worldData.pack.bake.lightGrid.maskDomains.runMaskDomain import MaskDomainMaterializer
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy


def source_collection_types(
    broad: MaskSourceCollector[object, int], ctx: LandcoverCollectContext,
    materializer: LandcoverMaterializer, policy: MaskCategoryPolicy,
) -> MaskSourceCollector[LandcoverCollectContext, ResolvedRegion]:
    narrow: MaskSourceCollector[LandcoverCollectContext, int] = broad
    assert_type(default_collect(narrow, ctx, policy, key=lambda value: value), list[int])
    return materializer


def light_adapter_types(adapter: LandcoverLightAdapter) -> MaskDomainMaterializer[ResolvedRegion]:
    return adapter
