"""Thin pure orchestration for ribbon grade sites."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.conditionNormalize import (
    normalize_condition,
)
from app.application.worldData.generators.terrain.relief.geomResolve import (
    ResolvedGeom,
    geom_resolve,
)
from app.application.worldData.generators.terrain.relief.kindRoll import kind_roll
from app.application.worldData.generators.terrain.relief.reliefEvents import (
    EVENT_GRADE_SKIP,
    EVENT_RESOLVE_FALLBACK,
    REASON_SCHEDULE_HOLE_SAFE_SLOPE,
    WHY_SCHEDULE_HOLE,
)
from app.application.worldData.generators.terrain.relief.reliefLog import (
    relief_info,
    relief_warning,
)
from app.application.worldData.generators.terrain.relief.slopeClassify import classify
from app.dataModel.terrain.relief.enums import ReliefSideKind, ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefGradeKnobs import ReliefGradeKnobs
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


def _attachment_defaults() -> tuple[bool | None, str | None, tuple[str, ...]]:
    """Canal knobs defaults from POJO (RELIEF-T-41 / R28). Raw omit until bake."""
    knobs = ReliefGradeKnobs.model_validate({
        "slope_weight": 1.0,
        "sheer_weight": 0.0,
    })
    return (
        knobs.earthen_canal,
        knobs.structure_canal,
        tuple(knobs.structure_refs),
    )


@dataclass(frozen=True, slots=True)
class RibbonGradeDecision:
    """Ribbon/edge grade site (road_shoulder / open_land / shore) — RELIEF-T-1.

    ``requested_length`` / ``geom`` are pre-clearance; bake shortens via §9.
    Canal knobs are raw (omit/`structure_canal` ref); resolve once at bake (T-51).
    """

    template_uid: str
    policy: ReliefSlopePolicy | None
    kind: ReliefSideKind | None
    requested_length: int
    h: int
    geom: ResolvedGeom | None
    earthen_canal: bool | None
    structure_refs: tuple[str, ...]
    reason: str
    skipped: bool = False
    structure_canal: str | None = None

    @classmethod
    def skipped_site(
        cls,
        *,
        template_uid: str,
        reason: str,
        h: int,
        requested_length: int,
        earthen_canal: bool | None,
        structure_refs: tuple[str, ...],
        structure_canal: str | None,
        policy: ReliefSlopePolicy | None = None,
    ) -> RibbonGradeDecision:
        """Factory for skip paths (no condition / slope_none) — RELIEF-T-40."""
        return cls(
            template_uid=template_uid,
            policy=policy,
            kind=None,
            requested_length=requested_length,
            h=h,
            geom=None,
            earthen_canal=earthen_canal,
            structure_refs=structure_refs,
            reason=reason,
            skipped=True,
            structure_canal=structure_canal,
        )


def grade_from_template(
    *,
    template: ReliefTemplate,
    template_uid: str,
    terrain_key: str,
    dz: int,
    world_seed: str,
    site_id: str,
) -> RibbonGradeDecision:
    """Classify + kindRoll + geom for one ribbon site."""
    h = abs(int(dz))
    earthen_default, canal_default, refs_default = _attachment_defaults()
    root_length = template.outward_length_cells()

    cond = template.condition_for(terrain_key)
    if cond is None:
        relief_info(
            EVENT_GRADE_SKIP,
            template_uid=template_uid,
            terrain=terrain_key,
            reason="no_condition",
            site_id=site_id,
        )
        return RibbonGradeDecision.skipped_site(
            template_uid=template_uid,
            reason="no_condition",
            h=h,
            requested_length=root_length,
            earthen_canal=earthen_default,
            structure_refs=refs_default,
            structure_canal=canal_default,
        )

    schedule = normalize_condition(cond)
    hit = classify(dz, schedule)
    if hit is None:
        # RELIEF-T-14 / R21: schedule hole → safe SLOPE (not silent skip)
        relief_warning(
            EVENT_RESOLVE_FALLBACK,
            context=template.context.value,
            why=WHY_SCHEDULE_HOLE,
            dz=dz,
            terrain=terrain_key,
            chosen_fallback=ReliefSideKind.SLOPE.value,
            site_id=site_id,
        )
        geom = geom_resolve(
            h=h, kind=ReliefSideKind.SLOPE, slope_length_cells=root_length,
        )
        return RibbonGradeDecision(
            template_uid=template_uid,
            policy=None,
            kind=ReliefSideKind.SLOPE,
            requested_length=geom.L,
            h=h,
            geom=geom,
            earthen_canal=earthen_default,
            structure_refs=refs_default,
            reason=REASON_SCHEDULE_HOLE_SAFE_SLOPE,
            skipped=False,
            structure_canal=canal_default,
        )

    if hit.policy == ReliefSlopePolicy.SLOPE_NONE:
        relief_info(
            EVENT_GRADE_SKIP,
            template_uid=template_uid,
            policy="slope_none",
            reason=hit.reason,
            site_id=site_id,
        )
        return RibbonGradeDecision.skipped_site(
            template_uid=template_uid,
            reason=hit.reason,
            h=h,
            requested_length=root_length,
            earthen_canal=earthen_default,
            structure_refs=refs_default,
            structure_canal=canal_default,
            policy=hit.policy,
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
    geom = geom_resolve(h=h, kind=kind, knobs=hit.knobs)
    relief_info(
        "grade_apply",
        template_uid=template_uid,
        policy=hit.policy.value,
        kind=kind.value,
        requested_length=geom.L,
        angle_deg=geom.angle_deg,
        earthen_canal=hit.knobs.earthen_canal,
        structure_canal=hit.knobs.structure_canal,
        reason=hit.reason,
        site_id=site_id,
    )
    return RibbonGradeDecision(
        template_uid=template_uid,
        policy=hit.policy,
        kind=kind,
        requested_length=geom.L,
        h=h,
        geom=geom,
        earthen_canal=hit.knobs.earthen_canal,
        structure_refs=tuple(hit.knobs.structure_refs),
        reason=hit.reason,
        skipped=False,
        structure_canal=hit.knobs.structure_canal,
    )
