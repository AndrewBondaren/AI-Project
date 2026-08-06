"""open_land light contributor — Wave D1 (relief grade, not MaskDomain paint)."""

from __future__ import annotations

import logging

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.openLandApply import (
    apply_open_land_grades,
)
from app.dataModel.masks.enums.maskDomainId import LightContributorId

logger = logging.getLogger(__name__)


class OpenLandContributor:
    name = LightContributorId.OPEN_LAND.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        intents = apply_open_land_grades(compose, ctx)
        logger.debug(
            "light_contributor_open_land | world=%s intents=%d applied=%d",
            ctx.world.world_uid,
            len(intents),
            sum(1 for i in intents if not i.skipped),
        )
