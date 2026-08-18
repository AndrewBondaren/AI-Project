"""Pick + ``grade_constrained`` on ``FrontGeometry`` after discover (R41-T-9).

Does not run inside ``fronts.py``. Does not mint uid or paint.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.discover.types import (
    FrontGeometry,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.application.worldData.generators.terrain.relief.pick.gradeConstrained import (
    grade_constrained,
)
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    RibbonGradeDecision,
)
from app.application.worldData.generators.terrain.relief.pick.templatePick import (
    pick_template,
    resolve_picked_template,
)
from app.application.worldData.pack.refine.detailedGradeFrontIdentity import (
    FrontBakeIdentity,
)
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.worldReliefPickPolicy import WorldReliefPickPolicy
from app.dataModel.terrain.relief.worldReliefTemplateRegistry import (
    WorldReliefTemplateRegistry,
)


@dataclass(frozen=True, slots=True)
class PickedFrontGrade:
    template_uid: str | None
    decision: RibbonGradeDecision


def pick_front_grade(
    front: FrontGeometry,
    identity: FrontBakeIdentity,
    *,
    registry: WorldReliefTemplateRegistry,
    policy: WorldReliefPickPolicy,
    world_seed: str,
    templates: Mapping[str, ReliefTemplate],
    occurrence_seq: int,
) -> PickedFrontGrade | None:
    """Template pick + envelope constrain. ``None`` = skip this front."""
    pick = pick_template(
        context=front.context,
        registry=registry,
        world_policy=policy,
        world_seed=world_seed,
        site_id=identity.site_id,
        occurrence_seq=occurrence_seq,
    )
    template = resolve_picked_template(pick, templates)
    if template is None:
        relief_debug(
            "grade_front_skip",
            why="no_template",
            site_id=identity.site_id,
            context=front.context.value,
        )
        return None
    decision = grade_constrained(
        template=template,
        template_uid=pick.template_uid or template.system_name,
        terrain_key=identity.terrain_key,
        dz=identity.dz,
        world_seed=world_seed,
        site_id=identity.site_id,
        path_length=int(front.path_length),
    )
    if decision.skipped or decision.kind is None or int(decision.h) < 1:
        relief_debug(
            "grade_front_skip",
            why="constrained",
            site_id=identity.site_id,
            skipped=decision.skipped,
        )
        return None
    return PickedFrontGrade(
        template_uid=pick.template_uid,
        decision=decision,
    )
