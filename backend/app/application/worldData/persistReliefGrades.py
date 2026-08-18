"""Persist bake-produced grades to SQL — tz_terrain_relief §8c / R43."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from app.application.worldData.generators.terrain.relief.volume.gradeInstanceFactory import (
    utc_now_iso,
)
from app.application.worldData.gradeInstanceMerge import apply_prior_cell_refs
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_relief_grades_persist_done,
    log_pack_relief_grades_persist_progress,
    log_pack_relief_grades_persist_start,
)
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem
from app.db.models.reliefGradeInstance import ReliefGradeInstanceRow
from app.db.models.reliefGradeSystem import ReliefGradeSystemRow
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository

# Heartbeat / sqlite executemany order — same ~5000 as TR-PERF-1 (R43).
UPSERT_BATCH_SIZE = 5000

_BulkUpsert = Callable[..., Awaitable[None]]


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
        structure_refs=list(inst.structure_refs),
        structure_canal=inst.structure_canal,
        template_uid=inst.template_uid,
        owner_uid=inst.owner_uid,
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
        owner_uid=system.owner_uid,
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
    system_list = list(systems or ())
    n_instances = len(instances)
    n_systems = len(system_list)
    started_at = log_pack_relief_grades_persist_start(
        world_uid,
        n_instances=n_instances,
        n_systems=n_systems,
        replace_world=replace_world,
    )

    prior_refs: dict[str, object] = {}
    if not replace_world and instances:
        for row in await repo.list_instances_by_uids(
            world_uid,
            [inst.grade_uid for inst in instances],
        ):
            prior_refs[row.grade_uid] = row.cell_refs

    created = utc_now_iso()
    system_rows = [system_to_row(system, created_at=created) for system in system_list]
    instance_rows = [
        instance_to_row(
            apply_prior_cell_refs(inst, prior_refs.get(inst.grade_uid)),
            created_at=created,
        )
        for inst in instances
    ]

    if replace_world or system_rows or instance_rows:
        async with repo.persist_session():
            if replace_world:
                await repo.delete_instances_for_world(world_uid)
            await _bulk_with_progress(
                repo.upsert_systems,
                system_rows,
                world_uid,
                kind="systems",
                started_at=started_at,
            )
            await _bulk_with_progress(
                repo.upsert_instances,
                instance_rows,
                world_uid,
                kind="instances",
                started_at=started_at,
            )

    log_pack_relief_grades_persist_done(
        world_uid,
        n_instances=n_instances,
        n_systems=n_systems,
        started_at=started_at,
    )
    return n_instances


async def _bulk_with_progress(
    upsert: _BulkUpsert,
    rows: Sequence[object],
    world_uid: str,
    *,
    kind: str,
    started_at: float,
) -> None:
    total = len(rows)
    if total == 0:
        return
    for offset in range(0, total, UPSERT_BATCH_SIZE):
        batch = rows[offset : offset + UPSERT_BATCH_SIZE]
        await upsert(batch)
        log_pack_relief_grades_persist_progress(
            world_uid,
            kind=kind,
            done=min(offset + len(batch), total),
            total=total,
            started_at=started_at,
        )
