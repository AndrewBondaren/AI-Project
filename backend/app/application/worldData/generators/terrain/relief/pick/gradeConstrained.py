"""Ontology envelope facade around ``grade_from_template`` — tz_terrain_relief R37.

Inner classify / kindRoll / ``geom_resolve`` stay as-is. This module clamps knobs
to ``ReliefOntologyEnvelopes``, then optionally restores L > h on the decision
when the envelope requires a gentle slope (R36i tails).
"""

from __future__ import annotations

from dataclasses import replace

from app.application.worldData.generators.terrain.relief.geom.geomResolve import (
    ResolvedGeom,
    angle_from_height_length,
    geom_resolve,
    partition_height,
)
from app.application.worldData.generators.terrain.relief.log.events import (
    EVENT_GRADE_SKIP,
    EVENT_INVALID_GEOM,
    REASON_ONTOLOGY_NO_FIT,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_info, relief_warning
from app.application.worldData.generators.terrain.relief.pick.gradePass import (
    RibbonGradeDecision,
    attachment_defaults,
    grade_from_template,
)
from app.application.worldData.generators.terrain.relief.sample.terrainMap import (
    map_system_terrain,
)
from app.dataModel.terrain.relief.enums import (
    ReliefSideKind,
    ReliefSlopePolicy,
)
from app.dataModel.terrain.relief.reliefGradeKnobs import coerce_geom_knobs
from app.dataModel.terrain.relief.reliefRoleCase import ReliefRoleCase
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.terrain.relief.reliefTerrainEnvelope import (
    ReliefOntologyEnvelopes,
    ReliefTerrainEnvelope,
)
from app.dataModel.worldPack.parentLightRefinePolicy import ParentLightRefinePolicy


def _skip(
    *,
    template: ReliefTemplate,
    template_uid: str,
    h: int,
    reason: str,
) -> RibbonGradeDecision:
    earthen, canal, refs = attachment_defaults()
    return RibbonGradeDecision.skipped_site(
        template_uid=template_uid,
        reason=reason,
        h=h,
        requested_length=template.outward_length_cells(),
        earthen_canal=earthen,
        structure_refs=refs,
        structure_canal=canal,
        policy=ReliefSlopePolicy.SLOPE_NONE,
    )


def _template_geom_knobs(
    template: ReliefTemplate,
    terrain_key: str,
    dz: int,
) -> tuple[int | None, float | None]:
    cond = template.condition_for(terrain_key)
    if cond is None:
        return template.slope_length_cells, template.target_angle_deg
    if dz > 0:
        case = cond.case_for(ReliefSlopePolicy.SLOPE_DOWN)
    elif dz < 0:
        case = cond.case_for(ReliefSlopePolicy.SLOPE_UP)
    else:
        return template.slope_length_cells, template.target_angle_deg
    if case.is_mode_a:
        knobs = case.mode_a_grade_knobs()
        return knobs.slope_length_cells, knobs.target_angle_deg
    mag = abs(int(dz))
    for band in case.bands or []:
        if mag < band.delta_z_min:
            continue
        if band.delta_z_max is not None and mag > band.delta_z_max:
            continue
        return band.slope_length_cells, band.target_angle_deg
    return template.slope_length_cells, template.target_angle_deg


def _clamp_knob_payload(
    payload: dict,
    envelope: ReliefTerrainEnvelope,
    h: int,
    *,
    is_none_policy: bool,
    plateau: int,
    length_cap: int | None = None,
) -> dict:
    out = dict(payload)
    if is_none_policy:
        if out.get("delta_z") is not None:
            out["delta_z"] = max(int(out["delta_z"]), plateau)
        return out
    length, angle, _why = coerce_geom_knobs(
        out.get("slope_length_cells"), out.get("target_angle_deg"),
    )
    if _why is not None:
        out["slope_length_cells"] = length
        out["target_angle_deg"] = angle
    length = envelope.slope_length_for(
        h,
        template_length=out.get("slope_length_cells"),
        template_angle_deg=out.get("target_angle_deg"),
        length_cap=length_cap,
    )
    if length is None:
        return out
    outcome = envelope.slope_outcome(h, length)
    sheer_l = ReliefTerrainEnvelope.canonical_sheer_length_cells()
    if outcome == "slope":
        out["slope_length_cells"] = length
        out["target_angle_deg"] = None
        override = envelope.weights_for_fitted_slope(h)
        if override is not None:
            out["slope_weight"], out["sheer_weight"] = override
    elif outcome == "sheer":
        out["slope_weight"] = 0.0
        out["sheer_weight"] = 1.0
        out["slope_length_cells"] = sheer_l
        out["target_angle_deg"] = None
    return out


def _clamp_template(
    template: ReliefTemplate,
    envelope: ReliefTerrainEnvelope,
    h: int,
    plateau: int,
    length_cap: int | None = None,
) -> ReliefTemplate:
    new_conds = []
    for cond in template.conditions:
        new_cases = []
        for case in cond.cases:
            dump = case.model_dump()
            is_none = case.policy == ReliefSlopePolicy.SLOPE_NONE
            if case.is_mode_a:
                dump = _clamp_knob_payload(
                    dump, envelope, h, is_none_policy=is_none, plateau=plateau,
                    length_cap=length_cap,
                )
            elif dump.get("bands"):
                dump["bands"] = [
                    _clamp_knob_payload(
                        band, envelope, h, is_none_policy=False, plateau=plateau,
                        length_cap=length_cap,
                    )
                    for band in dump["bands"]
                ]
            new_cases.append(ReliefRoleCase.model_validate(dump))
        new_conds.append(cond.model_copy(update={"cases": new_cases}))
    updates: dict = {"conditions": new_conds}
    root_l, root_a, root_why = coerce_geom_knobs(
        template.slope_length_cells, template.target_angle_deg,
    )
    if root_why is not None:
        template = template.model_copy(update={
            "slope_length_cells": root_l,
            "target_angle_deg": root_a,
        })
    root_l = envelope.slope_length_for(
        h,
        template_length=template.slope_length_cells,
        template_angle_deg=template.target_angle_deg,
        length_cap=length_cap,
    )
    if root_l is not None:
        updates["slope_length_cells"] = root_l
        updates["target_angle_deg"] = None
    return template.model_copy(update=updates)


def _restore_l_gt_h(
    decision: RibbonGradeDecision,
    envelope: ReliefTerrainEnvelope,
    h: int,
    wanted_l: int | None,
    *,
    site_id: str,
) -> RibbonGradeDecision:
    if (
        decision.skipped
        or decision.kind is not ReliefSideKind.SLOPE
        or not envelope.allow_l_gt_h
        or wanted_l is None
        or wanted_l < 1
        or not envelope.slope_fits(h, wanted_l)
    ):
        return decision
    geom = decision.geom
    if geom is not None and int(geom.L) >= int(wanted_l):
        return decision
    restored = ResolvedGeom(
        kind=ReliefSideKind.SLOPE,
        h=h,
        L=wanted_l,
        angle_deg=angle_from_height_length(h, wanted_l),
        steps=partition_height(h, wanted_l),
    )
    relief_info(
        "ontology_geom_restore",
        site_id=site_id,
        L_inner=None if geom is None else geom.L,
        L=wanted_l,
        angle_deg=restored.angle_deg,
    )
    return replace(decision, geom=restored, requested_length=wanted_l)


def _force_sheer_length(decision: RibbonGradeDecision) -> RibbonGradeDecision:
    """SHEER is always one XY column (R37/C31). Inner knobs may still carry SLOPE L."""
    if decision.skipped or decision.kind is not ReliefSideKind.SHEER:
        return decision
    length = ReliefTerrainEnvelope.canonical_sheer_length_cells()
    geom = decision.geom
    if (
        geom is not None
        and int(geom.L) == length
        and int(decision.requested_length) == length
        and geom.angle_deg is not None
    ):
        return decision
    restored = geom_resolve(
        h=decision.h,
        kind=ReliefSideKind.SHEER,
        slope_length_cells=length,
    )
    return replace(decision, geom=restored, requested_length=length)


def grade_constrained(
    *,
    template: ReliefTemplate,
    template_uid: str,
    terrain_key: str,
    dz: int,
    world_seed: str,
    site_id: str,
    envelopes: ReliefOntologyEnvelopes | None = None,
    z_band: int | None = None,
    path_length: int | None = None,
) -> RibbonGradeDecision:
    """Clamp template knobs to ontology envelope, then ``grade_from_template``.

    Stamp callers pass ``path_length`` (corridor / ribbon cap). Omit
    ``path_length`` = classify/construct without a ray: ``slope_length_for``
    may still apply ``L_min`` (plains unit ``dz=1`` → L=20). ``slope_fits``
    is θ-band only and does not veto short L.
    """
    h = abs(int(dz))
    table = envelopes or ReliefOntologyEnvelopes.canonical_defaults()
    mapped = map_system_terrain(terrain_key)
    envelope = (
        table.for_terrain(mapped) if mapped is not None else ReliefTerrainEnvelope()
    )
    z = (
        int(z_band)
        if z_band is not None
        else ParentLightRefinePolicy.canonical_defaults().z_band
    )
    if envelope.is_unconstrained() or not envelope.applies_to(template.context):
        return _force_sheer_length(
            grade_from_template(
                template=template,
                template_uid=template_uid,
                terrain_key=terrain_key,
                dz=dz,
                world_seed=world_seed,
                site_id=site_id,
            ),
        )

    plateau = envelope.plateau_abs_dz(z)
    tpl_l, tpl_a = _template_geom_knobs(template, terrain_key, dz)
    tpl_l, tpl_a, geom_why = coerce_geom_knobs(tpl_l, tpl_a)
    if geom_why is not None:
        relief_warning(
            EVENT_INVALID_GEOM,
            why=geom_why,
            template_uid=template_uid,
            terrain=terrain_key,
            site_id=site_id,
        )
    wanted = envelope.slope_length_for(
        h,
        template_length=tpl_l,
        template_angle_deg=tpl_a,
        length_cap=path_length,
    )
    if wanted is not None and envelope.slope_outcome(h, wanted) == "skip":
        relief_info(
            EVENT_GRADE_SKIP,
            template_uid=template_uid,
            terrain=terrain_key,
            reason=REASON_ONTOLOGY_NO_FIT,
            site_id=site_id,
        )
        return _skip(
            template=template,
            template_uid=template_uid,
            h=h,
            reason=REASON_ONTOLOGY_NO_FIT,
        )

    clamped = _clamp_template(
        template, envelope, h, plateau, length_cap=path_length,
    )
    decision = grade_from_template(
        template=clamped,
        template_uid=template_uid,
        terrain_key=terrain_key,
        dz=dz,
        world_seed=world_seed,
        site_id=site_id,
    )
    return _force_sheer_length(
        _restore_l_gt_h(
            decision, envelope, h, wanted, site_id=site_id,
        ),
    )
