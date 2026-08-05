"""Persist bake-produced grades to SQL — tz_terrain_relief §8c."""

from __future__ import annotations

from app.application.worldData.generators.terrain.relief.gradeInstanceFactory import (
    utc_now_iso,
)
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem
from app.db.models.reliefGradeInstance import ReliefGradeInstanceRow
from app.db.models.reliefGradeSystem import ReliefGradeSystemRow
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


def instance_to_row(
    inst: ReliefGradeInstance,
    *,
    created_at: str | None = None,
) -> ReliefGradeInstanceRow:
    return ReliefGradeInstanceRow(
        grade_uid=inst.grade_uid,
        world_uid=inst.world_uid,
        kind=inst.kind.value,
        height_cells=int(inst.height_cells),
        length_cells=int(inst.length_cells),
        cell_refs=[[int(x), int(y)] for x, y in inst.cell_refs],
        created_at=created_at or utc_now_iso(),
        angle_deg=inst.angle_deg,
        facing=inst.facing,
        earthen_canal=bool(inst.earthen_canal),
        template_uid=inst.template_uid,
        edge_uid=inst.edge_uid,
        site_id=inst.site_id,
        grade_system_uid=inst.grade_system_uid,
    )


def system_to_row(
    system: ReliefGradeSystem,
    *,
    created_at: str | None = None,
) -> ReliefGradeSystemRow:
    return ReliefGradeSystemRow(
        grade_system_uid=system.grade_system_uid,
        world_uid=system.world_uid,
        grade_instance_uids=list(system.grade_instance_uids),
        created_at=created_at or utc_now_iso(),
        edge_uid=system.edge_uid,
        display_name=system.display_name,
    )


async def persist_relief_grades(
    repo: IReliefGradeRepository,
    *,
    world_uid: str,
    instances: list[ReliefGradeInstance],
    systems: list[ReliefGradeSystem] | None = None,
    replace_world: bool = True,
) -> int:
    """Upsert grades for a world. ``replace_world`` clears prior rows first (re-bake)."""
    if replace_world:
        await repo.delete_instances_for_world(world_uid)
    created = utc_now_iso()
    for system in systems or ():
        await repo.upsert_system(system_to_row(system, created_at=created))
    for inst in instances:
        await repo.upsert_instance(instance_to_row(inst, created_at=created))
    return len(instances)
