"""T-3c catalog emit after pack persist — not pack files, not SQL upsert.

Caller: ``FineChunkRunner`` after ``FineChunkPersist.finish``.
SQL write is ``persist_relief_grades`` on the orchestrator.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from app.application.worldData.gradeInstanceMerge import merge_grade_instances
from app.application.worldData.gradeVertexSystem import emit_relief_grade_systems
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_grade_systems_emit_done,
    log_pack_grade_systems_emit_start,
)
from app.application.worldData.pack.refine.detailedGradeCatalog import TileFaceCatalog
from app.application.worldData.pack.refine.fineTileContext import VertexSlotSeam
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem

ChunkSeamTrace = tuple[ColumnRect, tuple[VertexSlotSeam, ...]]


def emit_fine_grade_catalog(
    instances: Sequence[ReliefGradeInstance],
    traces: Sequence[ChunkSeamTrace],
    catalog: TileFaceCatalog | None,
    *,
    world_uid: str,
) -> tuple[tuple[ReliefGradeInstance, ...], tuple[ReliefGradeSystem, ...], float]:
    """Merge instances then T-3c systems. ``emit_s`` is wall time for bake log."""
    if not instances:
        return (), (), 0.0
    merged = merge_grade_instances(tuple(instances))
    if not merged:
        return (), (), 0.0
    emit_t0 = log_pack_grade_systems_emit_start(
        world_uid, n_instances=len(merged),
    )
    grade_instances, grade_systems = emit_relief_grade_systems(
        merged,
        traces=traces,
        catalog=catalog,
    )
    emit_s = time.perf_counter() - emit_t0
    log_pack_grade_systems_emit_done(
        world_uid,
        n_instances=len(grade_instances),
        n_systems=len(grade_systems),
        started_at=emit_t0,
    )
    return grade_instances, grade_systems, emit_s
