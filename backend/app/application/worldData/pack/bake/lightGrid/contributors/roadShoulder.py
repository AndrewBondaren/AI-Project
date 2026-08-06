"""Road shoulder light contributor — grade after road paint (RELIEF-T-31).

Not a MaskDomain writer: consumes ``ctx.painted_road_edges`` from RoadContributor.
"""

from __future__ import annotations

import logging

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderApply import (
    apply_road_shoulder_grades,
)
from app.dataModel.masks.enums.maskDomainId import LightContributorId

logger = logging.getLogger(__name__)


class RoadShoulderContributor:
    name = LightContributorId.ROAD_SHOULDER.value

    def apply(self, compose: LightGridCompose, ctx: LightGridBakeContext) -> None:
        if not ctx.painted_road_edges:
            logger.debug(
                "light_contributor_road_shoulder | world=%s skipped=no_painted_edges",
                ctx.world.world_uid,
            )
            return

        shoulder_seq = 0
        applied_n = 0
        for painted in ctx.painted_road_edges:
            intents = apply_road_shoulder_grades(
                compose,
                ctx,
                owner_uid=painted.owner_uid,
                road_cells=set(painted.road_cells),
                object_policy=painted.object_policy,
                occurrence_start=shoulder_seq,
            )
            shoulder_seq += len(intents)
            applied_n += sum(1 for i in intents if not i.skipped)

        logger.debug(
            "light_contributor_road_shoulder | world=%s edges=%d intents=%d applied=%d",
            ctx.world.world_uid,
            len(ctx.painted_road_edges),
            shoulder_seq,
            applied_n,
        )
