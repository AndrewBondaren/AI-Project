"""Assemble GradeFormation write-set — canal-cut + instance + uid. No surface z write."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.canal.attachments import (
    knobs_extra_structure_refs,
    project_canal_draw,
)
from app.application.worldData.generators.terrain.relief.geom.facing import (
    CARDINAL_ORTHO_DELTAS,
    facing_wire,
)
from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    build_ribbon_grade_instance,
)
from app.application.worldData.generators.terrain.relief.log.log import relief_debug
from app.application.worldData.generators.terrain.relief.pick.ribbonGrade import RibbonGradeResult
from app.application.worldData.pack.refine.detailedGradeResult import GradeFormation
from app.application.worldData.pack.refine.meterGradeSurface import Coord
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance


def inherit_segment_uid(
    seeds: tuple[Coord, ...],
    uids: dict[Coord, str],
) -> str | None:
    """Reuse uid already on the ribbon. Exactly one neighbor uid; else None.

    Neighbor set is **cardinal only** (R41-T-6). Discover stays 8-way; inherit
    matches C29 chunk edges (ortho). A diagonal neighbor with a uid is another
    front (C15: one outward = one Instance) or a chunk corner — mint / catalog,
    do not glue. Ambiguous (two uids) → None. Not first-lock-wins (C41).
    """
    found: set[str] = set()
    for seed in seeds:
        for xy in (seed, *( (seed[0] + dx, seed[1] + dy) for dx, dy in CARDINAL_ORTHO_DELTAS )):
            uid = uids.get(xy)
            if uid:
                found.add(uid)
    if len(found) != 1:
        relief_debug(
            "grade_uid_inherit",
            hit=False,
            neighbor_count=len(found),
            neighbor_uids=tuple(sorted(found)) or None,
            seed_count=len(seeds),
            seed=min(seeds) if seeds else None,
        )
        return None
    uid = next(iter(found))
    relief_debug(
        "grade_uid_inherit",
        hit=True,
        grade_uid=uid,
        neighbor_count=1,
        seed_count=len(seeds),
        seed=min(seeds),
    )
    return uid


def instance_for_formation(
    result: RibbonGradeResult,
    formation: GradeFormation,
    *,
    world_uid: str,
    seeds: tuple[Coord, ...],
) -> ReliefGradeInstance:
    drawn = project_canal_draw(
        formation.canal,
        extra_structure_refs=knobs_extra_structure_refs(
            earthen_canal=result.decision.earthen_canal,
            structure_canal=result.decision.structure_canal,
            structure_refs=result.decision.structure_refs,
        ),
    )
    return build_ribbon_grade_instance(
        world_uid=world_uid,
        site_id=result.segment.site_id,
        seed=min(seeds),
        plan=formation.plan,
        cell_refs=formation.corridor,
        facing=facing_wire(formation.facing),
        earthen_canal=drawn.earthen_canal,
        structure_refs=drawn.structure_refs,
        structure_canal=drawn.structure_canal,
        template_uid=result.template_uid,
        owner_uid=result.segment.owner_uid,
        grade_uid=formation.grade_uid,
    )
