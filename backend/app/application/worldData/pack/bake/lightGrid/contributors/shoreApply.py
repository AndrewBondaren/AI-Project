"""shore ribbon grades — Wave D2 thin facade."""

from __future__ import annotations

from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.contextRibbonApply import (
    apply_context_ribbon_grades,
)
from app.application.worldData.pack.bake.lightGrid.contributors.shoreSample import (
    sample_shore_cells,
)
from app.application.worldData.pack.bake.lightGrid.ribbonIntent import (
    RibbonIntent,
)
from app.dataModel.terrain.relief.enums import ReliefContext


def apply_shore_grades(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    *,
    occurrence_start: int = 0,
) -> list[RibbonIntent]:
    """Hydro SHORE edge → ribbon Grade."""
    return apply_context_ribbon_grades(
        compose,
        ctx,
        context=ReliefContext.SHORE,
        sample_fn=sample_shore_cells,
        occurrence_start=occurrence_start,
    )
