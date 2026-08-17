"""DiscoveredFront → existing L2 volume / GradeFormation (C40 / R41-T-2).

Does not fork ``plan_ribbon_volume``. Discover does not write z/uid.
"""

from __future__ import annotations

from app.application.jsonValidation import canal_templates, relief_pick_policy
from app.application.worldData.generators.terrain.relief.canal.seedResolve import (
    aggregate_canals,
)
from app.application.worldData.generators.terrain.relief.discover.neighbors import (
    max_outward_k,
    step_k,
)
from app.application.worldData.generators.terrain.relief.discover.types import (
    Coord,
    DiscoveredFront,
)
from app.application.worldData.generators.terrain.relief.pick.ribbonGrade import (
    RibbonGradeResult,
)
from app.application.worldData.generators.terrain.relief.sample.ribbonSegmentize import (
    RibbonSegment,
)
from app.application.worldData.generators.terrain.relief.volume.volumeMaterialize import (
    plan_seed_volume,
    ribbon_sign_from_dz,
)
from app.application.worldData.pack.refine.detailedGradeCanalCut import (
    canal_for_seed,
    r36t_include_cut_end,
)
from app.application.worldData.pack.refine.detailedGradeCorridor import (
    r36t_corridor_cells,
)
from app.application.worldData.pack.refine.detailedGradeMaterialize import (
    instance_for_formation,
)
from app.application.worldData.pack.refine.detailedGradeResult import (
    DetailedGradeResult,
    GradeFormation,
)
from app.application.worldData.pack.refine.meterGradeSurface import MeterGradeSurface
from app.db.models.world import World


def apply_grade_paint_spec(
    front: DiscoveredFront,
    *,
    world: World,
    surface: MeterGradeSurface,
) -> DetailedGradeResult:
    """1D ``plan_ribbon_volume``, repeat ``z[k]`` across ``front_w`` onto corridor."""
    spec = front.spec
    decision = spec.decision
    kind = decision.kind
    if kind is None or decision.skipped or int(decision.h) < 1:
        return DetailedGradeResult.empty()
    if not spec.corridor:
        return DetailedGradeResult.empty()

    z_top = surface.z_at(spec.anchor_top)
    if z_top is None:
        return DetailedGradeResult.empty()
    L_eff = max_outward_k(spec.corridor, front.rim, spec.outward)
    if L_eff < 1:
        return DetailedGradeResult.empty()
    ks = [step_k(cell, front.rim, spec.outward) for cell in spec.corridor]
    sign = ribbon_sign_from_dz(int(front.dz))
    plan = plan_seed_volume(
        decision_geom=decision.geom,
        h=int(decision.h),
        kind=kind,
        L_eff=L_eff,
        z_road=int(z_top),
        sign=sign,
    )
    if plan is None or not plan.columns:
        return DetailedGradeResult.empty()

    by_k = {col.k: col.surface_z for col in plan.columns}
    overlay: dict[Coord, int] = {}
    for cell, k in zip(spec.corridor, ks, strict=True):
        if k is None or k not in by_k:
            continue
        overlay[cell] = by_k[k]
    wrote = tuple(cell for cell in spec.corridor if cell in overlay)
    if not wrote:
        return DetailedGradeResult.empty()

    segment = RibbonSegment(
        owner_uid=front.context.value,
        terrain_key=front.terrain_key,
        system_terrain=front.system_terrain,
        dz=int(front.dz),
        site_id=front.site_id,
        cell_coords=tuple(front.rim),
    )
    result = RibbonGradeResult(
        segment=segment,
        decision=decision,
        template_uid=front.template_uid,
    )
    canal = canal_for_seed(
        result,
        requested=max(0, int(decision.requested_length)),
        L_eff=int(plan.L),
        policy_rules=tuple(relief_pick_policy(world).canal_obstacle_policy),
        registry=canal_templates(world),
    )
    crest = {spec.anchor_top, *front.rim}
    cut = r36t_corridor_cells(
        wrote,
        crest,
        include_cut_end=r36t_include_cut_end(
            canal=canal,
            L_eff=int(plan.L),
            requested=max(0, int(decision.requested_length)),
        ),
    )
    allowed = set(cut) & set(spec.corridor)
    corridor = tuple(cell for cell in wrote if cell in allowed)
    overlay = {xy: z for xy, z in overlay.items() if xy in allowed}
    if not corridor:
        return DetailedGradeResult.empty()

    formation = GradeFormation(
        plan=plan,
        overlay=overlay,
        corridor=corridor,
        facing=spec.outward,
        canal=aggregate_canals([canal] if canal is not None else []),
        grade_uid=spec.grade_uid,
    )
    inst = instance_for_formation(
        result, formation, world_uid=world.world_uid, seeds=front.rim,
    )
    return formation.to_write_set(inst)
