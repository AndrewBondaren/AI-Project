"""Apply road_shoulder grade after road paint — thin facade (T-30/T-52 phase 5).

Wire: sample → grade → materialize → intent. Stamp/adapters live in sibling modules.
Sample SoT = footprint edge of ``road_cells`` (Q6 / Wave B1).
"""

from __future__ import annotations

from app.application.jsonValidation.worldRow import canal_templates, relief_pick_policy
from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_ROAD_SHOULDER_SKIP,
    WHY_EMPTY_SAMPLE,
    WHY_NO_ROAD_CELLS,
    WHY_NO_TEMPLATES,
    WHY_NOT_STAMPED,
)
from app.application.worldData.generators.terrain.relief.reliefLog import relief_debug
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    grade_road_shoulder_segments,
    segmentize_by_terrain,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderMaterialize import (
    materialize_segment,
)
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderSample import (
    sample_shoulder_cells,
)
from app.application.worldData.pack.bake.lightGrid.roadShoulderIntent import (
    RoadShoulderIntent,
    to_intent,
)
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
    if not road_cells:
        relief_debug(
            EVENT_ROAD_SHOULDER_SKIP,
            edge_uid=edge_uid,
            why=WHY_NO_ROAD_CELLS,
        )
        return []
    if not ctx.relief_templates_by_uid:
        relief_debug(
            EVENT_ROAD_SHOULDER_SKIP,
            edge_uid=edge_uid,
            why=WHY_NO_TEMPLATES,
        )
        return []

    tile_set = set(ctx.tiles)
    samples = sample_shoulder_cells(
        compose, road_cells, tile_set=tile_set,
    )
    if not samples:
        relief_debug(
            EVENT_ROAD_SHOULDER_SKIP,
            edge_uid=edge_uid,
            why=WHY_EMPTY_SAMPLE,
            road_cells=len(road_cells),
        )
        return []

    segments = segmentize_by_terrain(edge_uid=edge_uid, cells=samples)
    canal_reg = canal_templates(ctx.world)
    canal_rules = relief_pick_policy(ctx.world).canal_obstacle_policy
    results = grade_road_shoulder_segments(
        world=ctx.world,
        world_seed=bake_seed(ctx.world),
        segments=segments,
        templates_by_uid=ctx.relief_templates_by_uid,
        object_policy=object_policy,
        occurrence_start=occurrence_start,
    )
    intents: list[RoadShoulderIntent] = []
    for result in results:
        if result.decision.skipped or result.decision.kind is None:
            intents.append(to_intent(result, result.segment.cell_coords))
            continue
        mat = materialize_segment(
            compose,
            ctx,
            result,
            road_cells=road_cells,
            tile_set=tile_set,
            canal_registry=canal_reg,
            canal_rules=canal_rules,
        )
        if not mat.stamped:
            intents.append(
                to_intent(
                    result,
                    (),
                    skipped=True,
                    reason=mat.skip_why or WHY_NOT_STAMPED,
                    width=0,
                    canal=mat.canal,
                    extra_structure_refs=mat.extra_structure_refs,
                )
            )
            continue
        intents.append(
            to_intent(
                result,
                mat.stamped,
                width=mat.width_used,
                canal=mat.canal,
                extra_structure_refs=mat.extra_structure_refs,
            ),
        )
    ctx.road_shoulder_intents.extend(intents)
    relief_debug(
        "road_shoulder_apply",
        edge_uid=edge_uid,
        segments=len(segments),
        applied=sum(1 for i in intents if not i.skipped),
    )
    return intents
