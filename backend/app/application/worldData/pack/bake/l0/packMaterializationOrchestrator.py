"""Pack L0 materialization — light_bake / full_bake share one body (WP-27).

L0 only (Job boundaries). Entry/L2 — ``EntryRefineOrchestrator`` /
``POST …/refine-from-entry``, never this path.
"""

from __future__ import annotations
from app.application.worldData.planning.composition.surfacePlanningEntry import SurfacePlanningEntry

import logging
import time
from collections.abc import Callable

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanWaitControl
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.worldData.planning.composition.surfacePlanningCapture import SurfacePlanningCapture, mountain_template_inputs
from app.application.worldData.planning.guards.sourcePublication import SourcePublicationGuard
from app.dataModel.validation.enums.resolutionMode import ResolutionMode

from app.application.worldData.materialize.shared.persistResult import PersistResult
from app.application.worldData.materialize.surface.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.application.worldData.pack.climate.climatePackBakeOrchestrator import ClimatePackBakeOrchestrator
from app.application.templateLibrary.loadReliefTemplatesForWorld import (
    load_relief_templates_for_world,
)
from app.application.worldData.persist.persistReliefGrades import persist_relief_grades
from app.application.worldData.pack.bake.l0.worldMapBakeOrchestrator import WorldMapBakeOrchestrator
from app.db.repositories.iReliefGradeRepository import IReliefGradeRepository
from app.application.worldData.pack.refine.entry.entryRefineOrchestrator import EntryRefineOrchestrator
from app.application.worldData.pack.refine.fine.chunk.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.refine.fine.fineScenePathRefine import FineScenePathRefine
from app.application.worldData.pack.refine.fine.fineRectDrain import FineRectDrain
from app.application.worldData.pack.bake.l0.locationsIndexBake import build_locations_index
from app.application.worldData.pack.bake.finalize.packBakeFinalize import finalize_pack_on_world
from app.application.worldData.pack.bake.plan.packTilePlanner import PackTilePlanner
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.materialize.shared.parallelPolicy import (
    resolve_climate_workers,
    resolve_terrain_workers,
)
from app.application.templateLibrary.templateSnapshotLoader import TemplateSnapshotLoader
from app.core.generationLogging import generation_world_log
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.bake.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.bake.packBakeMode import PackBakeMode
from app.dataModel.worldPack.bake.packTilePlan import PackTilePlanScope
from app.application.worldData.materialize.terrain.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.db.database import Database
from app.db.repositories.iWorldRepository import IWorldRepository
from app.db.repositories.iRegionStateRepository import IRegionStateRepository
from app.application.worldData.regions.regionStateSnapshot import load_region_state_snapshot
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_bake_done,
    log_pack_bake_start,
)


class PackMaterializationOrchestrator:
    """L0 world_map / climate coarse bake. Entry refine on ``EntryRefineOrchestrator``."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        world_map: WorldMapBakeOrchestrator | None = None,
        scene_path: FineScenePathRefine | None = None,
        rect_drain: FineRectDrain | None = None,
        entry: EntryRefineOrchestrator | None = None,
        job_repo: IChunkRefineJobRepository | None = None,
        world_repository: IWorldRepository | None = None,
        db: Database | None = None,
        bake_defaults: PackBakeDefaults | None = None,
        read_context: PackReadContext | None = None,
        read_context_for: Callable[[str], PackReadContext] | None = None,
        climate_bake: ClimatePackBakeOrchestrator | None = None,
        tile_planner: PackTilePlanner | None = None,
        relief_loader: TemplateSnapshotLoader | None = None,
        relief_grade_repo: IReliefGradeRepository | None = None,
        region_state_repo: IRegionStateRepository | None = None,
        planning: SurfacePlanningAssembler | None = None,
        capture: SurfacePlanningCapture | None = None,
        publication_guard: SourcePublicationGuard | None = None,
    ) -> None:
        self._planning, self._capture, self._publication_guard = planning, capture, publication_guard
        self._terrain = terrain
        self._world_map = world_map or WorldMapBakeOrchestrator()
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()
        self._planner = tile_planner or PackTilePlanner(bake_defaults=self._defaults)
        if world_repository is not None and db is None:
            raise ValueError("pack finalization requires caller database")
        self._world_repository = world_repository
        self._db = db
        self._read_context = read_context
        self._read_context_for = read_context_for
        self._relief_loader = relief_loader
        self._relief_grade_repo = relief_grade_repo
        self._region_state_repo = region_state_repo
        if entry is not None:
            self._entry = entry
            self._climate = climate_bake or entry.climate_bake
        else:
            self._entry, self._climate = _default_entry_stack(
                terrain,
                scene_path=scene_path,
                rect_drain=rect_drain,
                job_repo=job_repo,
                read_context=read_context,
                bake_defaults=self._defaults,
                climate_bake=climate_bake,
                relief_loader=relief_loader,
                relief_grade_repo=relief_grade_repo,
            )

    @property
    def terrain(self) -> TerrainBatchOrchestrator:
        return self._terrain

    @property
    def relief_loader(self) -> TemplateSnapshotLoader | None:
        return self._relief_loader

    @property
    def relief_grade_repo(self) -> IReliefGradeRepository | None:
        return self._relief_grade_repo

    @property
    def entry(self) -> EntryRefineOrchestrator:
        return self._entry

    @property
    def tile_planner(self) -> PackTilePlanner:
        return self._planner

    async def materialize_light_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
    ) -> MaterializationJobReport:
        with generation_world_log(world_uid, mode="light"):
            return await self._materialize_l0_pack(
                world_uid,
                world,
                locations,
                writer,
                mat_ctx,
                scope="light",
                max_tiles=max_tiles,
                nodes=nodes,
                edges=edges,
                wait=wait, resolve_ctx=resolve_ctx,
                anchor_x=anchor_x,
                anchor_y=anchor_y,
            )

    async def materialize_full_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
    ) -> MaterializationJobReport:
        """full_bake — same L0 pipeline, all macro-tiles in world_bounds / resolved AABB."""
        with generation_world_log(world_uid, mode="full"):
            return await self._materialize_l0_pack(
                world_uid,
                world,
                locations,
                writer,
                mat_ctx,
                scope="full",
                max_tiles=None,
                nodes=nodes,
                edges=edges,
                wait=wait, resolve_ctx=resolve_ctx,
            )

    async def _materialize_l0_pack(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        scope: PackTilePlanScope,
        max_tiles: int | None = None,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        wait: PlanWaitControl,
        resolve_ctx: ResolveContext | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
    ) -> MaterializationJobReport:
        if self._planning is None or self._capture is None:
            raise ValueError("surface planning dependencies required")
        request_ctx = resolve_ctx if resolve_ctx is not None else ResolveContext()
        if request_ctx.validate_only:
            raise ValueError("validation cannot materialize a pack")
        relief_templates = await _load_relief_templates(self._relief_loader, world)
        templates = mountain_template_inputs(relief_templates)
        entry = SurfacePlanningEntry(self._planning, self._capture)
        captured = entry.capture_view(world, locations, mode=ResolutionMode.RUNTIME,
            mountain_templates=templates, resolve_ctx=request_ctx)
        prepared = entry.prepare_captured(
            captured, world=world, wait=wait, resolve_ctx=request_ctx)
        if prepared is None:
            raise ValueError("surface terrain context unavailable")
        surface_bundle, working = prepared
        if self._region_state_repo is None:
            raise ValueError("region state repository required for materialization")
        region_states = await load_region_state_snapshot(self._region_state_repo, world_uid)
        plan = self._planner.plan(
            world, locations, scope=scope, max_tiles=max_tiles,
        )
        tiles = plan.tile_tuples()
        bake_mode: PackBakeMode = "full" if scope == "full" else "light"
        climate_workers = resolve_climate_workers(mat_ctx, world)
        bake_t0 = log_pack_bake_start(
            world_uid,
            tile_cap=plan.cap_applied if plan.cap_applied is not None else -1,
            tiles_planned=len(tiles),
            locations=len(locations),
            terrain_workers=resolve_terrain_workers(mat_ctx, world),
            climate_workers=climate_workers,
        )
        drain = self._defaults.background_drain_per_request
        if self._entry.has_job_repo and drain > 0:
            await self._entry.drain_persisted(
                world_uid, world, locations, writer, mat_ctx, surface_bundle,
                max_jobs=drain,
                region_state_snapshot=region_states,
                working=working,
            )

        climate_result: PersistResult | None = None
        climate_coarse_samples = 0
        climate_fine_tiles = 0
        climate_result, climate_coarse_samples = await self._climate.bake_coarse(
            world, surface_bundle, writer, mat_ctx, locations=locations,
            working=working,
        )

        locations_index = build_locations_index(locations, world)
        writer.write_locations_index(locations_index)

        # Incremental: still bake all planned tiles (overwrite) so content stays consistent
        world_map_cells = self._world_map.bake_tiles(
            world, locations, writer, tiles,
            surface_bundle=surface_bundle,
            locations_index=locations_index,
            nodes=nodes, edges=edges, wait=wait,
            bake_mode=bake_mode,
            relief_templates_by_uid=relief_templates,
            region_state_snapshot=region_states,
            working=working,
        )
        await _persist_bake_relief_grades(
            self._relief_grade_repo,
            world,
            self._world_map.last_relief_grade_instances,
        )
        terrain_result = PersistResult.from_counts(world_map_cells, world_map_cells)

        climate_fine_tiles = await self._climate.bake_fine_for_l0_policy(
            world, surface_bundle, writer, mat_ctx, tiles, locations,
            scope=scope,
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            working=working,
        )
        if climate_fine_tiles and climate_result is not None:
            climate_result = PersistResult.from_counts(
                climate_result.total + climate_fine_tiles,
                climate_result.succeeded + climate_fine_tiles,
            )
        elif climate_fine_tiles:
            climate_result = PersistResult.from_counts(climate_fine_tiles, climate_fine_tiles)

        if self._world_repository is not None:
            read_ctx = self._read_context
            if read_ctx is None and self._read_context_for is not None:
                read_ctx = self._read_context_for(world_uid)
            assert self._db is not None
            if self._publication_guard is None:
                raise ValueError("source publication guard required")
            async with self._db.transaction_if_needed():
                current = await self._publication_guard.require_fresh(captured, mode=ResolutionMode.RUNTIME,
                    mountain_templates=templates, resolve_ctx=request_ctx)
                writer.recalc_manifest_counters()
                await finalize_pack_on_world(
                    self._world_repository, current, writer,
                    db_path=self._db.path, read_context=read_ctx,
                )

        workers = resolve_terrain_workers(mat_ctx, world)
        elapsed_s = time.perf_counter() - bake_t0
        queue_depth = len(self._entry.refine_queue)
        log_pack_bake_done(
            world_uid,
            world_map_cells=world_map_cells,
            chunks_done=0,
            chunks_total=0,
            queue_depth=queue_depth,
            started_at=bake_t0,
        )
        return MaterializationJobReport(
            terrain=terrain_result,
            climate=climate_result,
            chunks_done=0,
            chunks_total=0,
            terrain_workers=workers,
            climate_workers=climate_workers,
            elapsed_s=elapsed_s,
            world_map_cells=world_map_cells,
            refine_queue_depth=queue_depth,
            climate_coarse_samples=climate_coarse_samples or None,
            climate_fine_tiles=climate_fine_tiles or None,
        )


async def _load_relief_templates(
    relief_loader: TemplateSnapshotLoader | None,
    world: World,
) -> dict[str, ReliefTemplate]:
    """Unbound loader → warning + empty set; templates are optional inputs."""
    if relief_loader is None:
        logging.getLogger(__name__).warning(
            "relief | pack bake: relief_loader unbound world=%s — "
            "mountain/road_shoulder templates not preloaded",
            world.world_uid,
        )
        return {}
    return await load_relief_templates_for_world(relief_loader, world)


async def _persist_bake_relief_grades(
    relief_grade_repo: IReliefGradeRepository | None,
    world: World,
    instances,
) -> None:
    if relief_grade_repo is None:
        return
    n_grades = await persist_relief_grades(
        relief_grade_repo,
        world_uid=world.world_uid,
        instances=instances,
        replace_world=False,
    )
    logging.getLogger(__name__).info(
        "relief | persisted grade instances world=%s n=%d",
        world.world_uid,
        n_grades,
    )


def _default_entry_stack(
    terrain: TerrainBatchOrchestrator,
    *,
    scene_path: FineScenePathRefine | None,
    rect_drain: FineRectDrain | None,
    job_repo: IChunkRefineJobRepository | None,
    read_context: PackReadContext | None,
    bake_defaults: PackBakeDefaults,
    climate_bake: ClimatePackBakeOrchestrator | None,
    relief_loader: TemplateSnapshotLoader | None,
    relief_grade_repo: IReliefGradeRepository | None,
) -> tuple[EntryRefineOrchestrator, ClimatePackBakeOrchestrator]:
    """Default refine stack wiring when ``entry`` is not injected."""
    climate = climate_bake or ClimatePackBakeOrchestrator(
        read_context=read_context,
        bake_defaults=bake_defaults,
    )
    runner = FineChunkRunner(terrain)
    scene = scene_path or FineScenePathRefine(
        terrain,
        runner=runner,
        relief_grade_repo=relief_grade_repo,
    )
    drain = rect_drain or FineRectDrain(
        terrain,
        runner=runner,
        relief_loader=relief_loader,
        relief_grade_repo=relief_grade_repo,
    )
    return EntryRefineOrchestrator(
        scene,
        drain,
        job_repo=job_repo,
        bake_defaults=bake_defaults,
        climate_bake=climate,
        read_context=read_context,
    ), climate
