"""detailed_bake refine loop — one tile pass over a resolved ``DetailedScopePlan``.

Parent-light gate + per-tile refine + aggregate + grade persist; scope
selection lives in ``detailedBakeScope``, ordering/logging — in the
orchestrator.
"""

from __future__ import annotations
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps

import time
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry

from app.application.worldData.generators.coordinates import map_cell_fine_span
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.generators.terrain.relief.discover.timings import (
    GradePipelineTimings,
)
from app.application.worldData.materialize.surface.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.detailed.detailedBakeScope import DetailedScopePlan
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.parentLightLoad import require_parent_light
from app.application.worldData.pack.refine.fine.fineChunkRunner import FineChunkRunner
from app.application.worldData.persist.persistReliefGrades import persist_relief_grades
from app.application.worldData.materialize.shared.persistResult import PersistResult
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance
from app.dataModel.terrain.relief.reliefGradeSystem import ReliefGradeSystem
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.bake.gradePipelineStages import GradePipelineStages
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


@dataclass
class DetailedRefineAggregate:
    persist: PersistResult = field(default_factory=lambda: PersistResult.from_counts(0, 0))
    chunks_written: int = 0
    tiles_refined: int = 0
    fine_surface_z: dict[tuple[int, int], int] = field(default_factory=dict)
    grade_instances: list[ReliefGradeInstance] = field(default_factory=list)
    grade_systems: list[ReliefGradeSystem] = field(default_factory=list)
    materialize_s: float = 0.0
    grade_s: float = 0.0
    pipeline_s: GradePipelineTimings = field(default_factory=GradePipelineTimings)


async def refine_detailed_tiles(
    runner: FineChunkRunner,
    world: World,
    locations: list[NamedLocation],
    writer: WorldPackWriter,
    mat_ctx: MaterializationContext,
    surface_bundle: SurfacePlanBundle,
    plan: DetailedScopePlan,
    *,
    phase: str = "detailed",
    relief_templates_by_uid: dict[str, ReliefTemplate] | None = None,
    stages: GradePipelineStages | None = None,
    region_state_snapshot: Mapping[str, StateSnapshotEntry],
    working: SurfaceWorkingMaps,
) -> DetailedRefineAggregate:
    """Require L0 parent light per tile, then refine every rect of the plan."""
    tile_macro = map_cell_fine_span(world)
    reader = WorldPackReader(writer.paths)
    cache = writer.parent_light_cache
    for gx, gy in plan.tiles:
        require_parent_light(
            world.world_uid, gx, gy,
            reader=reader, cache=cache, tile_macro=tile_macro,
        )

    aggregate = DetailedRefineAggregate()
    for gx, gy in plan.tiles:
        rects = plan.rects_for_tile(gx, gy)
        if not rects:
            continue
        refined = await runner.refine_rects(
            world, locations, writer, mat_ctx, surface_bundle,
            gx, gy, rects, plan.location_volumes,
            refine_role=plan.refine_role,
            phase=phase,
            relief_templates_by_uid=relief_templates_by_uid,
            stages=stages or GradePipelineStages.off(),
            region_state_snapshot=region_state_snapshot,
            working=working,
        )
        for key, z in refined.fine_surface_z.items():
            prev = aggregate.fine_surface_z.get(key)
            if prev is None or z > prev:
                aggregate.fine_surface_z[key] = z
        aggregate.persist = PersistResult.from_counts(
            aggregate.persist.total + refined.persist.total,
            aggregate.persist.succeeded + refined.persist.succeeded,
            failed=aggregate.persist.failed + refined.persist.failed,
        )
        aggregate.chunks_written += refined.wilderness_chunks_written
        aggregate.tiles_refined += 1
        aggregate.grade_instances.extend(refined.grade_instances)
        aggregate.grade_systems.extend(refined.grade_systems)
        aggregate.materialize_s += refined.materialize_s
        aggregate.grade_s += refined.grade_s
        aggregate.pipeline_s = aggregate.pipeline_s.added(refined.pipeline_s)
        if plan.expected_chunks_for_status is not None:
            writer.recalc_wilderness_status(
                gx, gy,
                expected_chunks=plan.expected_chunks_for_status(gx, gy),
            )
    return aggregate


async def persist_detailed_grades(
    relief_grade_repo: IReliefGradeRepository | None,
    world_uid: str,
    aggregate: DetailedRefineAggregate,
) -> float:
    if relief_grade_repo is None or not aggregate.grade_instances:
        return 0.0
    persist_t0 = time.perf_counter()
    await persist_relief_grades(
        relief_grade_repo,
        world_uid=world_uid,
        instances=aggregate.grade_instances,
        systems=aggregate.grade_systems,
        replace_world=False,
    )
    return time.perf_counter() - persist_t0
