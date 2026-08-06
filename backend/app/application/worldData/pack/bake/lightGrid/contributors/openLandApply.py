"""open_land ribbon grades — Wave D1 thin facade."""

from __future__ import annotations

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.contextRibbonApply import (
    apply_context_ribbon_grades,
)
from app.application.worldData.pack.bake.lightGrid.contributors.openLandSample import (
    sample_open_land_cells,
)
from app.application.worldData.pack.bake.lightGrid.roadShoulderIntent import (
    RoadShoulderIntent,
)
from app.dataModel.terrain.relief.enums import ReliefContext


def apply_open_land_grades(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    *,
    occurrence_start: int = 0,
) -> list[RoadShoulderIntent]:
    """Δz plains/forest sites → ribbon Grade."""
    return apply_context_ribbon_grades(
        compose,
        ctx,
        context=ReliefContext.OPEN_LAND,
        sample_fn=sample_open_land_cells,
        occurrence_start=occurrence_start,
    )
