"""Persist refine grade instances — shared drain for scene/path/rect zones."""

from __future__ import annotations

from app.application.worldData.pack.refine.fine.fineRefineResult import FineRefineResult
from app.application.worldData.persist.persistReliefGrades import persist_relief_grades
from app.db.models.world import World
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


async def persist_refine_grade_instances(
    relief_grade_repo: IReliefGradeRepository | None,
    world: World,
    result: FineRefineResult,
) -> None:
    if relief_grade_repo is None or not result.grade_instances:
        return
    await persist_relief_grades(
        relief_grade_repo,
        world_uid=world.world_uid,
        instances=list(result.grade_instances),
        systems=list(result.grade_systems),
        replace_world=False,
    )
