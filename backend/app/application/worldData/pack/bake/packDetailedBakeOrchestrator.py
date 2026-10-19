"""detailed_bake — offline L2 for location territory and/or wilderness tiles.

Facade owns ordering/logging/deps; scope resolution — ``detailedBakeScope``;
the tile refine loop and grade persist — ``detailedBakeRefine``.
See docs/tz_world_pack_storage.md § Bake modes; .cursor/plans/detailed-bake-smell-fixes-done.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.relief.discover.timings import (
    GradePipelineTimings,
)
from app.application.worldData.materialize.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.detailedBakeRefine import (
    DetailedRefineAggregate,
    persist_detailed_grades,
    refine_detailed_tiles,
)
from app.application.worldData.pack.bake.detailedBakeScope import (
    DetailedScopePlan,
    resolve_detailed_scope,
)
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_detailed_bake_done,
    log_pack_detailed_bake_skip_not_in_index,
    log_pack_detailed_bake_start,
)
from app.application.worldData.pack.climate.climatePackBakeOrchestrator import (
    ClimatePackBakeOrchestrator,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.refine.fine.fineChunkRunner import FineChunkRunner
from app.application.worldData.materialize.persistResult import PersistResult
from app.application.templateLibrary.templateSnapshotLoader import TemplateSnapshotLoader
from app.application.worldData.materialize.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.core.generationLogging import generation_world_log
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.bake.detailedBakeScope import (
    DetailedBakeRequest,
    DetailedBakeScopeKind,
)
from app.dataModel.worldPack.bake.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.bake.gradePipelineStages import GradePipelineStages
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository


@dataclass(frozen=True)
class PackDetailedBakeResult:
    scope: DetailedBakeScopeKind
    terrain: PersistResult
    tiles_refined: int = 0
    wilderness_chunks: int = 0
    climate_fine_tiles: int = 0
    location_uid: str | None = None
    l2_s: float = 0.0
    grade_persist_s: float = 0.0
    pipeline_s: GradePipelineTimings = field(default_factory=GradePipelineTimings)
    grade_mill: bool = False
    grade_paint: bool = False


class PackDetailedBakeOrchestrator:
    """Offline L2 detailed bake — location and wilderness scopes share one refine loop."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        runner: FineChunkRunner | None = None,
        climate_bake: ClimatePackBakeOrchestrator | None = None,
        bake_defaults: PackBakeDefaults | None = None,
        relief_loader: TemplateSnapshotLoader | None = None,
        relief_grade_repo: IReliefGradeRepository | None = None,
    ) -> None:
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()
        self._runner = runner or FineChunkRunner(terrain)
        self._climate = climate_bake or ClimatePackBakeOrchestrator(
            bake_defaults=self._defaults,
        )
        self._relief_loader = relief_loader
        self._relief_grade_repo = relief_grade_repo

    async def bake(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
    ) -> PackDetailedBakeResult:
        with generation_world_log(world.world_uid, mode="detailed"):
            log_pack_detailed_bake_start(
                world.world_uid,
                scope=request.scope,
                grade_mill=request.grade_mill,
                grade_paint=request.grade_paint,
            )
            return await self._bake_in_log_scope(
                world, locations, writer, mat_ctx, surface_ctx, request,
            )

    async def _bake_in_log_scope(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
    ) -> PackDetailedBakeResult:
        relief_templates: dict[str, ReliefTemplate] = {}
        if request.stages.mill and self._relief_loader is not None:
            from app.application.templateLibrary.loadReliefTemplatesForWorld import (
                load_relief_templates_for_world,
            )

            relief_templates = await load_relief_templates_for_world(
                self._relief_loader, world,
            )
        if request.scope == "location":
            return await self._bake_location_scope(
                world, locations, writer, mat_ctx, surface_ctx, request,
                relief_templates=relief_templates,
            )
        return await self._bake_wilderness_scope(
            world, locations, writer, mat_ctx, surface_ctx, request,
            relief_templates=relief_templates,
        )

    async def _bake_location_scope(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
        *,
        relief_templates: dict[str, ReliefTemplate],
    ) -> PackDetailedBakeResult:
        plan = resolve_detailed_scope(world, locations, writer, request)
        if plan is None:
            return self._skip_location_result(world, request)
        return await self._run(
            world, locations, writer, mat_ctx, surface_ctx, request, plan,
            relief_templates=relief_templates,
        )

    async def _bake_wilderness_scope(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
        *,
        relief_templates: dict[str, ReliefTemplate],
    ) -> PackDetailedBakeResult:
        plan = resolve_detailed_scope(world, locations, writer, request)
        assert plan is not None
        return await self._run(
            world, locations, writer, mat_ctx, surface_ctx, request, plan,
            relief_templates=relief_templates,
        )

    def _skip_location_result(
        self,
        world: World,
        request: DetailedBakeRequest,
    ) -> PackDetailedBakeResult:
        location_uid = request.location_uid
        assert location_uid is not None
        log_pack_detailed_bake_skip_not_in_index(
            world.world_uid, location_uid=location_uid,
        )
        log_pack_detailed_bake_done(
            world.world_uid,
            scope="location",
            tiles=0,
            chunks=0,
            materialize_s=0.0,
            grade_s=0.0,
            l2_s=0.0,
            grade_persist_s=0.0,
            grade_mill=request.grade_mill,
            grade_paint=request.grade_paint,
        )
        return PackDetailedBakeResult(
            scope="location",
            terrain=PersistResult.from_counts(0, 0),
            location_uid=location_uid,
            grade_mill=request.grade_mill,
            grade_paint=request.grade_paint,
        )

    async def _run(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        request: DetailedBakeRequest,
        plan: DetailedScopePlan,
        *,
        relief_templates: dict[str, ReliefTemplate],
    ) -> PackDetailedBakeResult:
        l2_t0 = time.perf_counter()
        aggregate = await self._refine_tiles(
            world, locations, writer, mat_ctx, surface_ctx, plan,
            relief_templates_by_uid=relief_templates,
            stages=request.stages,
        )
        l2_s = time.perf_counter() - l2_t0

        climate_fine_tiles = 0
        if plan.location_uid is not None and self._defaults.detailed_include_climate_fine:
            for gx, gy in plan.tiles:
                if await self._climate.bake_fine_tile_with_parent(
                    world, surface_ctx, writer, mat_ctx, gx, gy,
                    l2_surface_z=aggregate.fine_surface_z or None,
                    locations=locations,
                    require_parent=True,
                ):
                    climate_fine_tiles += 1

        writer.recalc_manifest_counters()
        writer.save_manifest()
        grade_persist_s = await persist_detailed_grades(
            self._relief_grade_repo, world.world_uid, aggregate,
        )
        log_pack_detailed_bake_done(
            world.world_uid,
            scope=request.scope,
            tiles=aggregate.tiles_refined,
            chunks=aggregate.chunks_written,
            materialize_s=aggregate.materialize_s,
            grade_s=aggregate.grade_s,
            l2_s=l2_s,
            grade_persist_s=grade_persist_s,
            pipeline=aggregate.pipeline_s,
            grade_mill=request.grade_mill,
            grade_paint=request.grade_paint,
        )
        return PackDetailedBakeResult(
            scope=request.scope,
            terrain=aggregate.persist,
            tiles_refined=aggregate.tiles_refined,
            wilderness_chunks=aggregate.chunks_written,
            climate_fine_tiles=climate_fine_tiles,
            location_uid=plan.location_uid,
            l2_s=l2_s,
            grade_persist_s=grade_persist_s,
            pipeline_s=aggregate.pipeline_s,
            grade_mill=request.grade_mill,
            grade_paint=request.grade_paint,
        )

    async def _refine_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        plan: DetailedScopePlan,
        *,
        phase: str = "detailed",
        relief_templates_by_uid: dict[str, ReliefTemplate] | None = None,
        stages: GradePipelineStages | None = None,
    ) -> DetailedRefineAggregate:
        return await refine_detailed_tiles(
            self._runner,
            world, locations, writer, mat_ctx, surface_ctx, plan,
            phase=phase,
            relief_templates_by_uid=relief_templates_by_uid,
            stages=stages,
        )
