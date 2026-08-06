"""open_land ribbon grades — Wave D1 thin facade."""

from __future__ import annotations

from app.application.jsonValidation import terrain_masks
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.openLandSample import (
    sample_open_land_cells,
)
from app.application.worldData.pack.bake.lightGrid.contributors.ribbonGradeApply import (
    apply_ribbon_grades,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderBarrierApply import (
    apply_road_shoulder_barriers,
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
    """Δz plains/forest sites → ribbon Grade; BAR-1 if structure_refs."""
    if not ctx.relief_templates_by_uid:
        return []
    context = ReliefContext.OPEN_LAND
    masks = terrain_masks(ctx.world)
    road_key = masks.default_roads.system_terrain
    tile_set = set(ctx.tiles)
    samples, ref_cells = sample_open_land_cells(
        compose, tile_set=tile_set, road_key=road_key,
    )
    intents = apply_ribbon_grades(
        compose,
        ctx,
        owner_uid=context.value,
        ref_cells=ref_cells,
        samples=samples,
        context=context,
        occurrence_start=occurrence_start,
    )
    if intents:
        apply_road_shoulder_barriers(compose, ctx)
    return intents
