"""Apply road_shoulder grade after road paint — thin facade (T-30/T-52 phase 5).

Wire: sample → shared ``apply_ribbon_grades`` (early-exit owned there).
"""

from __future__ import annotations

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
    tile_set = set(ctx.tiles)
    samples = sample_shoulder_cells(
        compose, road_cells, tile_set=tile_set,
    ) if road_cells else []
    return apply_ribbon_grades(
        compose,
        ctx,
        owner_uid=edge_uid,
        ref_cells=road_cells,
        samples=samples,
        context=ReliefContext.ROAD_SHOULDER,
        object_policy=object_policy,
        occurrence_start=occurrence_start,
    )
