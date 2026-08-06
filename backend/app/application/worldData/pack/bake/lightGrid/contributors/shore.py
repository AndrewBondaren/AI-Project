"""shore light contributor — Wave D2 (relief grade; hydro roles consumed only)."""

from __future__ import annotations

import logging

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.shoreApply import (
    apply_shore_grades,
)
from app.dataModel.masks.enums.maskDomainId import LightContributorId

logger = logging.getLogger(__name__)


class ShoreContributor:
    name = LightContributorId.SHORE.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        intents = apply_shore_grades(compose, ctx)
        logger.debug(
            "light_contributor_shore | world=%s intents=%d applied=%d",
            ctx.world.world_uid,
            len(intents),
            sum(1 for i in intents if not i.skipped),
        )
