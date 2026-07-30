"""Thin pure orchestration for ribbon grade sites."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.conditionNormalize import (
    normalize_condition,
)
from app.application.worldData.generators.terrain.relief.kindRoll import kind_roll
from app.application.worldData.generators.terrain.relief.reliefLog import (
    relief_info,
    relief_warning,
)
from app.application.worldData.generators.terrain.relief.slopeClassify import classify
from app.dataModel.terrain.relief.enums import ReliefSideKind, ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


@dataclass(frozen=True, slots=True)
class RibbonGradeDecision:
    """Ribbon/edge grade site (road_shoulder / open_land / shore) — RELIEF-T-1."""

    template_uid: str
    policy: ReliefSlopePolicy | None
    kind: ReliefSideKind | None
    width: int
    earthen_canal: bool
    structure_refs: tuple[str, ...]
    reason: str
    skipped: bool = False


def grade_from_template(
    *,
    template: ReliefTemplate,
    template_uid: str,
    terrain_key: str,
    dz: int,
    world_seed: str,
    site_id: str,
) -> RibbonGradeDecision:
    """Classify + kindRoll for one ribbon site; skip on slope_none / missing condition."""
    cond = template.condition_for(terrain_key)
    if cond is None:
        relief_info(
            "grade_skip",
            template_uid=template_uid,
            terrain=terrain_key,
            reason="no_condition",
            site_id=site_id,
        )
        return RibbonGradeDecision(
            template_uid=template_uid,
            policy=None,
            kind=None,
            width=template.shoulder_width_cells,
            earthen_canal=False,
            structure_refs=(),
            reason="no_condition",
            skipped=True,
        )

    schedule = normalize_condition(cond)
    hit = classify(dz, schedule)
    if hit is None:
        # RELIEF-T-14 / R21: schedule hole → safe SLOPE (not silent skip)
        relief_warning(
            "r21_fallback",
            context=template.context.value,
            why="schedule_hole",
            dz=dz,
            terrain=terrain_key,
            chosen_fallback="SLOPE",
            site_id=site_id,
        )
        return RibbonGradeDecision(
            template_uid=template_uid,
            policy=None,
            kind=ReliefSideKind.SLOPE,
            width=template.shoulder_width_cells,
            earthen_canal=False,
            structure_refs=(),
            reason="schedule_hole_r21_slope",
            skipped=False,
        )

    if hit.policy == ReliefSlopePolicy.SLOPE_NONE:
        relief_info(
            "grade_skip",
            template_uid=template_uid,
            policy="slope_none",
            reason=hit.reason,
            site_id=site_id,
        )
        return RibbonGradeDecision(
            template_uid=template_uid,
            policy=hit.policy,
            kind=None,
            width=template.shoulder_width_cells,
            earthen_canal=False,
            structure_refs=(),
            reason=hit.reason,
            skipped=True,
        )

    assert hit.knobs is not None
    kind = kind_roll(
        world_seed=world_seed,
        context=template.context.value,
        template_uid=template_uid,
        site_id=site_id,
        slope_weight=hit.knobs.slope_weight,
        sheer_weight=hit.knobs.sheer_weight,
    )
    relief_info(
        "grade_apply",
        template_uid=template_uid,
        policy=hit.policy.value,
        kind=kind.value,
        width=hit.knobs.shoulder_width_cells,
        earthen_canal=hit.knobs.earthen_canal,
        reason=hit.reason,
        site_id=site_id,
    )
    return RibbonGradeDecision(
        template_uid=template_uid,
        policy=hit.policy,
        kind=kind,
        width=hit.knobs.shoulder_width_cells,
        earthen_canal=hit.knobs.earthen_canal,
        structure_refs=hit.knobs.structure_refs,
        reason=hit.reason,
        skipped=False,
    )
