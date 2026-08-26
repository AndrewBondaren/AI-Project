"""Build ``ReliefGradeInstance`` / ``ReliefGradeSystem`` — tz_terrain_relief §8c / R8."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.application.worldData.generators.terrain.relief.log.log import (
    relief_debug,
)
from app.application.worldData.generators.terrain.relief.volume.volumeMaterialize import (
    RibbonVolumePlan,
)
from app.dataModel.terrain.relief.enums import ReliefSideKind
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem

UID_PART_SEP = "|"
WHY_SIDE_ATTACH = "side_attach"
WHY_T3C_SAME_VERTEX = "t3c_same_vertex"


def _uid_digest(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return (
        f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-"
        f"{digest[16:20]}-{digest[20:32]}"
    )


def make_seeded_uid(*, world_seed: str, site_id: str) -> str:
    """R36w catalog / interior uid — namespace ``world_seed``, not cell seed."""
    return _uid_digest(UID_PART_SEP.join((world_seed, site_id)))


def make_grade_uid(*, world_uid: str, site_id: str, seed: tuple[int, int]) -> str:
    """Deterministic uid for re-bake upsert (legacy mint; catalog uses ``make_seeded_uid``)."""
    return _uid_digest(
        UID_PART_SEP.join((world_uid, site_id, f"{seed[0]},{seed[1]}"))
    )


def make_grade_system_uid(*, world_uid: str, site_id: str) -> str:
    key = UID_PART_SEP.join((world_uid, "grade_system", site_id))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return (
        f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-"
        f"{digest[16:20]}-{digest[20:32]}"
    )


def build_ribbon_grade_instance(
    *,
    world_uid: str,
    site_id: str,
    seed: tuple[int, int],
    plan: RibbonVolumePlan,
    cell_refs: tuple[tuple[int, int], ...],
    facing: str | None,
    earthen_canal: bool = False,
    structure_refs: tuple[str, ...] = (),
    structure_canal: str | None = None,
    template_uid: str | None = None,
    owner_uid: str | None = None,
    grade_uid: str | None = None,
) -> ReliefGradeInstance:
    """One Grade per successfully stamped seed strip (constant θ)."""
    if not cell_refs:
        raise ValueError("build_ribbon_grade_instance requires non-empty cell_refs")
    kind = plan.kind
    face = None if kind is ReliefSideKind.SHEER else facing
    inst = ReliefGradeInstance(
        grade_uid=grade_uid or make_grade_uid(
            world_uid=world_uid, site_id=site_id, seed=seed,
        ),
        world_uid=world_uid,
        kind=kind,
        height_cells=plan.h,
        length_cells=plan.L,
        cell_refs=list(cell_refs),
        angle_deg=plan.angle_deg,
        facing=face,
        earthen_canal=earthen_canal,
        structure_refs=list(structure_refs),
        structure_canal=structure_canal,
        template_uid=template_uid,
        owner_uid=owner_uid,
        site_id=site_id,
        grade_system_uid=None,
    )
    relief_debug(
        "grade_instance_create",
        grade_uid=inst.grade_uid,
        world_uid=inst.world_uid,
        kind=inst.kind.value,
        height_cells=inst.height_cells,
        length_cells=inst.length_cells,
        angle_deg=inst.angle_deg,
        facing=inst.facing,
        cell_count=len(inst.cell_refs),
        seed=seed,
        site_id=inst.site_id,
        template_uid=inst.template_uid,
        owner_uid=inst.owner_uid,
        earthen_canal=inst.earthen_canal,
        structure_refs=list(inst.structure_refs),
        structure_canal=inst.structure_canal,
    )
    return inst


def build_relief_grade_system(
    *,
    world_uid: str,
    site_id: str,
    grades: list[ReliefGradeInstance],
    why: str,
    owner_uid: str | None = None,
    display_name: str | None = None,
) -> ReliefGradeSystem:
    """Create system when steepness changes (≥2 grades). Logs why + members (R36l / R8)."""
    if len(grades) < 2:
        raise ValueError(
            "ReliefGradeSystem requires ≥2 grades (R36l); "
            f"got {len(grades)} — leave lone Grade without system"
        )
    grade_instance_uids = [g.grade_uid for g in grades]
    kinds = [g.kind.value for g in grades]
    angles = [g.angle_deg for g in grades]
    system = ReliefGradeSystem(
        grade_system_uid=make_grade_system_uid(world_uid=world_uid, site_id=site_id),
        world_uid=world_uid,
        grade_instance_uids=grade_instance_uids,
        owner_uid=owner_uid,
        display_name=display_name,
    )
    # DEBUG: per-system emit — INFO on console blocked the bake (stdout pipe).
    relief_debug(
        "grade_system_create",
        grade_system_uid=system.grade_system_uid,
        world_uid=world_uid,
        why=why,
        grade_count=len(grade_instance_uids),
        grade_instance_uids=grade_instance_uids,
        kinds=kinds,
        angles=angles,
        site_id=site_id,
        owner_uid=owner_uid,
        display_name=display_name,
    )
    relief_debug(
        "grade_system_members",
        grade_system_uid=system.grade_system_uid,
        members=[
            {
                "grade_uid": g.grade_uid,
                "kind": g.kind.value,
                "h": g.height_cells,
                "L": g.length_cells,
                "angle_deg": g.angle_deg,
                "cell_count": len(g.cell_refs),
            }
            for g in grades
        ],
    )
    return system


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
