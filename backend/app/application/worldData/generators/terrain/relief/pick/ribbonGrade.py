"""Ribbon grade sites — pick + classify (R20–R28 data out).

Segmentize: ``ribbonSegmentize`` (RELIEF-T-32). This module = pick/grade only.
Pure consumer: emits RibbonGradeDecision with raw canal knobs.
Registry/policy resolve happens once in bake (RELIEF-T-51).
Barrier stamp (RELIEF-BAR-1) was L0 bake; outdoor ribbon removed (R36u-T-8).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.jsonValidation.worldRow import (
    relief_pick_policy,
    relief_template_registry,
)
from app.application.worldData.generators.terrain.relief.pick.gradeConstrained import (
    grade_constrained,
)
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    RibbonGradeDecision,
)
from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_RIBBON_GRADE_APPLY,
    EVENT_RIBBON_SKIP_GRADE,
    WHY_NO_TEMPLATE_BODY,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_info
from app.application.worldData.generators.terrain.relief.sample.ribbonSegmentize import (
    RibbonSegment,
)
from app.application.worldData.generators.terrain.relief.pick.templatePick import (
    pick_template,
    resolve_picked_template,
)
from app.dataModel.terrain.relief.enums import ReliefContext
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import ObjectReliefPickPolicy
from app.db.models.world import World

__all__ = [
    "RibbonGradeResult",
    "RibbonSegment",
    "grade_ribbon_segments",
]


@dataclass(frozen=True, slots=True)
class RibbonGradeResult:
    segment: RibbonSegment
    decision: RibbonGradeDecision
    template_uid: str | None


def grade_ribbon_segments(
    *,
    world: World,
    world_seed: str,
    segments: list[RibbonSegment],
    templates_by_uid: dict[str, ReliefTemplate],
    object_policy: ObjectReliefPickPolicy | None = None,
    occurrence_start: int = 0,
    context: ReliefContext = ReliefContext.ROAD_SHOULDER,
) -> list[RibbonGradeResult]:
    """Grade ribbon segments for ``context`` (road_shoulder / open_land / shore / ravine)."""
    registry = relief_template_registry(world)
    world_policy = relief_pick_policy(world)
    results: list[RibbonGradeResult] = []
    seq = occurrence_start
    for segment in segments:
        pick = pick_template(
            context=context,
            registry=registry,
            world_policy=world_policy,
            world_seed=world_seed,
            site_id=segment.site_id,
            occurrence_seq=seq,
            object_policy=object_policy,
        )
        seq += 1
        template = resolve_picked_template(pick, templates_by_uid)
        if template is None:
            relief_info(
                EVENT_RIBBON_SKIP_GRADE,
                context=context.value,
                site_id=segment.site_id,
                why=WHY_NO_TEMPLATE_BODY,
                template_uid=pick.template_uid,
            )
            continue
        decision = grade_constrained(
            template=template,
            template_uid=pick.template_uid or template.system_name,
            terrain_key=segment.terrain_key,
            dz=segment.dz,
            world_seed=world_seed,
            site_id=segment.site_id,
        )
        results.append(
            RibbonGradeResult(
                segment=segment,
                decision=decision,
                template_uid=pick.template_uid,
            )
        )
        relief_info(
            EVENT_RIBBON_GRADE_APPLY,
            context=context.value,
            site_id=segment.site_id,
            template_uid=pick.template_uid,
            policy_level=pick.policy_level,
            skipped=decision.skipped,
            kind=None if decision.kind is None else decision.kind.value,
            earthen_canal=decision.earthen_canal,
            structure_canal=decision.structure_canal,
            structure_refs=list(decision.structure_refs),
            width=decision.requested_length,
        )
    return results
