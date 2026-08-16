"""Thin pure orchestration for ribbon grade sites."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.generators.terrain.relief.pick.conditionNormalize import (
    normalize_condition,
)
from app.application.worldData.generators.terrain.relief.geom.geomResolve import (
    ResolvedGeom,
    angle_from_height_length,
    geom_resolve,
    length_from_target_angle,
    partition_height,
)
from app.application.worldData.generators.terrain.relief.pick.kindRoll import kind_roll
from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_SKIP,
    EVENT_INVALID_GEOM,
    EVENT_RESOLVE_FALLBACK,
    REASON_SCHEDULE_HOLE_SAFE_SLOPE,
    WHY_SCHEDULE_HOLE,
)
from app.application.worldData.generators.terrain.relief.log.log import (
    relief_info,
    relief_warning,
)
from app.application.worldData.generators.terrain.relief.pick.slopeClassify import classify
from app.dataModel.terrain.relief.enums import ReliefSideKind, ReliefSlopePolicy
from app.dataModel.terrain.relief.reliefGradeKnobs import (
    ReliefGradeKnobs,
    coerce_geom_knobs,
)
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate


def attachment_defaults() -> tuple[bool | None, str | None, tuple[str, ...]]:
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
    """Ribbon/edge grade site (road_shoulder / open_land / shore / ravine) — RELIEF-T-1.

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


def _warn_invalid_geom(*, reason: str, site_id: str, template_uid: str, **fields: object) -> None:
    relief_warning(
        EVENT_INVALID_GEOM,
        why=reason,
        site_id=site_id,
        template_uid=template_uid,
        **fields,
    )


def _fallback_slope_length(h: int) -> int:
    return length_from_target_angle(
        max(1, int(h)),
        ReliefGradeKnobs.INVALID_GEOM_FALLBACK_ANGLE_DEG,
    )


def _slope_geom_for_length(h: int, length: int) -> ResolvedGeom:
    length_i = max(1, int(length))
    h_i = max(0, int(h))
    return ResolvedGeom(
        kind=ReliefSideKind.SLOPE,
        h=h_i,
        L=length_i,
        angle_deg=angle_from_height_length(h_i, length_i),
        steps=partition_height(h_i, length_i),
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
    earthen_default, canal_default, refs_default = attachment_defaults()
    _root_l, _root_a, root_why = coerce_geom_knobs(
        template.slope_length_cells, template.target_angle_deg,
    )
    if root_why is not None:
        _warn_invalid_geom(
            reason=root_why,
            site_id=site_id,
            template_uid=template_uid,
            where="root",
        )
        root_length = _fallback_slope_length(h) if h >= 1 else 1
    else:
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
        if root_why is not None and h >= 1:
            geom = _slope_geom_for_length(h, root_length)
        return RibbonGradeDecision(
            template_uid=template_uid,
            policy=None,
            kind=ReliefSideKind.SLOPE,
            requested_length=geom.L,
            h=h,
            geom=geom if geom.L >= 1 else None,
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
    knobs, geom_why = hit.knobs.coerced_geom()
    if geom_why is not None:
        _warn_invalid_geom(
            reason=geom_why,
            site_id=site_id,
            template_uid=template_uid,
            policy=hit.policy.value,
        )
    kind = kind_roll(
        world_seed=world_seed,
        context=template.context.value,
        template_uid=template_uid,
        site_id=site_id,
        slope_weight=knobs.slope_weight,
        sheer_weight=knobs.sheer_weight,
    )
    geom = geom_resolve(h=h, kind=kind, knobs=knobs)
    if geom_why is not None and kind is ReliefSideKind.SLOPE and h >= 1:
        geom = _slope_geom_for_length(h, _fallback_slope_length(h))
    relief_info(
        "grade_apply",
        template_uid=template_uid,
        policy=hit.policy.value,
        kind=kind.value,
        requested_length=geom.L,
        angle_deg=geom.angle_deg,
        earthen_canal=knobs.earthen_canal,
        structure_canal=knobs.structure_canal,
        reason=hit.reason,
        site_id=site_id,
    )
    return RibbonGradeDecision(
        template_uid=template_uid,
        policy=hit.policy,
        kind=kind,
        requested_length=geom.L,
        h=h,
        geom=geom if geom.L >= 1 else None,
        earthen_canal=knobs.earthen_canal,
        structure_refs=tuple(knobs.structure_refs),
        reason=hit.reason,
        skipped=False,
        structure_canal=knobs.structure_canal,
    )
