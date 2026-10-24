"""Mountain contributor — thin MaskDomain runner (tz_map_light_bake)."""

from __future__ import annotations

from app.application.worldData.generators.terrain.mountains.materializer import (
    MountainMaskMaterializer,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.dataModel.masks.enums.maskDomainId import LightContributorId


class MountainContributor:
    name = LightContributorId.MOUNTAIN.value

    def __init__(self, materializer: MountainMaskMaterializer | None = None) -> None:
        self._materializer = materializer or MountainMaskMaterializer()

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        self._materializer.apply_plan(compose, ctx)
