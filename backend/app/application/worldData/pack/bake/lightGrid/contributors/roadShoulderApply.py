"""Apply road_shoulder grade after road paint — thin facade (T-30/T-52 phase 5).

Wire: sample → shared ``apply_ribbon_grades``. Sample SoT = footprint edge (Q6).
"""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_RIBBON_SKIP,
    WHY_EMPTY_SAMPLE,
    WHY_NO_REF_CELLS,
    WHY_NO_TEMPLATES,
)
from app.application.worldData.generators.terrain.relief.reliefLog import relief_debug
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.ribbonGradeApply import (
    apply_ribbon_grades,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderSample import (
    sample_shoulder_cells,
)
from app.application.worldData.pack.bake.lightGrid.roadShoulderIntent import (
    RoadShoulderIntent,
)
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy


def apply_road_shoulder_grades(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    *,
    edge_uid: str,
    road_cells: set[tuple[int, int]],
    object_policy: ObjectReliefPickPolicy | None = None,
    occurrence_start: int = 0,
) -> list[RoadShoulderIntent]:
    """Grade one edge's shoulders; mutate compose z/facing; append intents."""
    context = ReliefContext.ROAD_SHOULDER
    if not road_cells:
        relief_debug(
            EVENT_RIBBON_SKIP,
            edge_uid=edge_uid,
            context=context.value,
            why=WHY_NO_REF_CELLS,
        )
        return []
    if not ctx.relief_templates_by_uid:
        relief_debug(
            EVENT_RIBBON_SKIP,
            edge_uid=edge_uid,
            context=context.value,
            why=WHY_NO_TEMPLATES,
        )
        return []

    tile_set = set(ctx.tiles)
    samples = sample_shoulder_cells(
        compose, road_cells, tile_set=tile_set,
    )
    if not samples:
        relief_debug(
            EVENT_RIBBON_SKIP,
            edge_uid=edge_uid,
            context=context.value,
            why=WHY_EMPTY_SAMPLE,
            ref_cells=len(road_cells),
        )
        return []

    return apply_ribbon_grades(
        compose,
        ctx,
        owner_uid=edge_uid,
        ref_cells=road_cells,
        samples=samples,
        context=context,
        object_policy=object_policy,
        occurrence_start=occurrence_start,
    )
