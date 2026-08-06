"""Shared ribbon grade wire — sample in → materialize → intent (Wave D).

Used by road_shoulder / open_land / shore. ``ref_cells`` = abutment footprint
(road / uphill / shore role); seeds grow outward away from it.
"""

from __future__ import annotations

from app.application.jsonValidation.worldRow import canal_templates, relief_pick_policy
from app.application.worldData.generators.terrain.relief.bakeSeed import bake_seed
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_RIBBON_GRADE_APPLY,
    EVENT_RIBBON_SKIP,
    WHY_EMPTY_SAMPLE,
    WHY_NO_REF_CELLS,
    WHY_NO_TEMPLATES,
    WHY_NOT_STAMPED,
)
from app.application.worldData.generators.terrain.relief.reliefLog import relief_debug
from app.application.worldData.generators.terrain.relief.ribbonSegmentize import (
    segmentize_by_terrain,
)
from app.application.worldData.generators.terrain.relief.roadShoulderGrade import (
    grade_road_shoulder_segments,
)
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext
from app.application.worldData.pack.bake.lightGrid.compose import LightGridCompose
from app.application.worldData.pack.bake.lightGrid.contributors.roadShoulderMaterialize import (
    materialize_segment,
)
from app.application.worldData.pack.bake.lightGrid.roadShoulderIntent import (
    RoadShoulderIntent,
    to_intent,
)
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy

SampleCell = tuple[tuple[int, int], str, int]


def apply_ribbon_grades(
    compose: LightGridCompose,
    ctx: LightGridBakeContext,
    *,
    owner_uid: str,
    ref_cells: set[tuple[int, int]],
    samples: list[SampleCell],
    context: ReliefContext,
    object_policy: ObjectReliefPickPolicy | None = None,
    occurrence_start: int = 0,
) -> list[RoadShoulderIntent]:
    """Segmentize → grade(context) → materialize; append intents to bake ctx."""
    if not ref_cells:
        relief_debug(
            EVENT_RIBBON_SKIP,
            owner_uid=owner_uid,
            context=context.value,
            why=WHY_NO_REF_CELLS,
        )
        return []
    if not ctx.relief_templates_by_uid:
        relief_debug(
            EVENT_RIBBON_SKIP,
            owner_uid=owner_uid,
            context=context.value,
            why=WHY_NO_TEMPLATES,
        )
        return []
    if not samples:
        relief_debug(
            EVENT_RIBBON_SKIP,
            owner_uid=owner_uid,
            context=context.value,
            why=WHY_EMPTY_SAMPLE,
            ref_cells=len(ref_cells),
        )
        return []

    tile_set = set(ctx.tiles)
    segments = segmentize_by_terrain(edge_uid=owner_uid, cells=samples)
    canal_reg = canal_templates(ctx.world)
    canal_rules = relief_pick_policy(ctx.world).canal_obstacle_policy
    results = grade_road_shoulder_segments(
        world=ctx.world,
        world_seed=bake_seed(ctx.world),
        segments=segments,
        templates_by_uid=ctx.relief_templates_by_uid,
        object_policy=object_policy,
        occurrence_start=occurrence_start,
        context=context,
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
            ref_cells=ref_cells,
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
    ctx.ribbon_intents.extend(intents)
    relief_debug(
        EVENT_RIBBON_GRADE_APPLY,
        owner_uid=owner_uid,
        context=context.value,
        segments=len(segments),
        applied=sum(1 for i in intents if not i.skipped),
    )
    return intents
