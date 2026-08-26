"""Read grade identity from the SQL catalog (R43).

Cell ``system_grade_uid`` is always an Instance uid (R36l / C11). Membership
in a System is ``Instance.grade_system_uid`` when a catalog row exists
(T-3c or Q3-attach).
Bake slot / ``occ`` / side parent are not stored.

Write path: ``emit_relief_grade_systems`` then ``persist_relief_grades``.
"""

from __future__ import annotations

from app.application.worldData.persistReliefGrades import (
    instance_from_row,
    system_from_row,
)
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


async def load_grade_instance(
    repo: IReliefGradeRepository,
    *,
    world_uid: str,
    grade_uid: str,
) -> ReliefGradeInstance | None:
    rows = await repo.list_instances_by_uids(world_uid, [grade_uid])
    if not rows:
        return None
    return instance_from_row(rows[0])


async def load_grade_system(
    repo: IReliefGradeRepository,
    *,
    world_uid: str,
    grade_system_uid: str,
) -> ReliefGradeSystem | None:
    rows = await repo.list_systems_by_uids(world_uid, [grade_system_uid])
    if not rows:
        return None
    return system_from_row(rows[0])


async def load_grade_membership(
    repo: IReliefGradeRepository,
    *,
    world_uid: str,
    instance_uid: str,
) -> tuple[ReliefGradeInstance | None, ReliefGradeSystem | None]:
    """Instance for a cell uid, plus System if the FK is set and the row exists."""
    instance = await load_grade_instance(
        repo, world_uid=world_uid, grade_uid=instance_uid,
    )
    if instance is None or not instance.grade_system_uid:
        return instance, None
    system = await load_grade_system(
        repo, world_uid=world_uid, grade_system_uid=instance.grade_system_uid,
    )
    return instance, system
