"""Pack-backed materialization facade — world map light + fine-terrain scene refine."""

from __future__ import annotations

import time

from app.application.worldData.persistResult import PersistResult
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    prepare_surface_terrain_context,
)
from app.application.worldData.materializationContext import (
    MaterializationContext,
    MaterializationJobReport,
)
from app.application.worldData.pack.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.chunkRefineWorker import ChunkRefineWorker
from app.application.worldData.pack.climateFinePending import ClimateFinePending
from app.application.worldData.pack.climatePackBakeOrchestrator import ClimatePackBakeOrchestrator
from app.application.worldData.pack.entryAnchorTracker import EntryAnchorTracker
from app.application.worldData.pack.worldMapBakeOrchestrator import WorldMapBakeOrchestrator
from app.application.worldData.pack.fineTerrainRefineOrchestrator import FineTerrainRefineOrchestrator
from app.application.worldData.pack.locationsIndexBake import build_locations_index
from app.application.worldData.pack.packBakeFinalize import finalize_pack_on_world
from app.application.worldData.pack.pathHeading import resolve_path_heading
from app.application.worldData.pack.packReadContext import PackReadContext
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.application.worldData.parallelPolicy import resolve_terrain_workers
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.application.worldData.worldService import WorldService
from app.core.appSettings import app_settings
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.application.worldData.pack.packBakeLog import (
    log_pack_bake_done,
    log_pack_bake_start,
    log_pack_drain_persisted_done,
    log_pack_drain_persisted_start,
    log_pack_jobs_persisted,
    log_pack_queue_enqueue,
)


class PackMaterializationOrchestrator:
    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        world_map: WorldMapBakeOrchestrator | None = None,
        fine_terrain: FineTerrainRefineOrchestrator | None = None,
        job_repo: IChunkRefineJobRepository | None = None,
        world_service: WorldService | None = None,
        bake_defaults: PackBakeDefaults | None = None,
        read_context: PackReadContext | None = None,
        climate_bake: ClimatePackBakeOrchestrator | None = None,
    ) -> None:
        self._terrain = terrain
        self._world_map = world_map or WorldMapBakeOrchestrator()
        self._fine_terrain = fine_terrain or FineTerrainRefineOrchestrator(terrain)
        self._anchors = EntryAnchorTracker()
        self._queue = ChunkRefineQueue(max_workers=1)
        self._climate_fine = ClimateFinePending()
        self._climate = climate_bake or ClimatePackBakeOrchestrator(read_context=read_context)
        self._worker = ChunkRefineWorker(
            self._fine_terrain,
            job_repo=job_repo,
            climate_bake=self._climate,
            climate_fine=self._climate_fine,
        )
        self._jobs = job_repo
        self._world_service = world_service
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()

    @property
    def refine_queue(self) -> ChunkRefineQueue:
        return self._queue

    @property
    def anchor_tracker(self) -> EntryAnchorTracker:
        return self._anchors

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
        hydrology_generator: HydrologyGeneratorService | None = None,
        anchor_x: int | None = None,
        anchor_y: int | None = None,
        heading_dx: int | None = None,
        heading_dy: int | None = None,
        refine_scene: bool = True,
    ) -> MaterializationJobReport:
        tile_cap = max_tiles if max_tiles is not None else self._defaults.max_tiles_light
        tiles = self._terrain.plan_bootstrap_tiles(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator, max_tiles=tile_cap,
        )
        bake_t0 = log_pack_bake_start(
            world_uid,
            tile_cap=tile_cap,
            tiles_planned=len(tiles),
            refine_scene=refine_scene,
            locations=len(locations),
            terrain_workers=resolve_terrain_workers(mat_ctx, world),
        )
        surface_ctx = prepare_surface_terrain_context(
            world, locations, nodes=nodes, edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if surface_ctx is not None and self._jobs is not None:
            drain_t0 = log_pack_drain_persisted_start(
                world_uid,
                max_jobs=max(self._defaults.background_drain_per_request, 1),
            )
            drained = await self._worker.drain_persisted(
                world_uid, world, locations, writer, mat_ctx, surface_ctx,
                max_jobs=max(self._defaults.background_drain_per_request, 1),
            )
            log_pack_drain_persisted_done(world_uid, processed=drained, started_at=drain_t0)

        climate_result: PersistResult | None = None
        climate_coarse_samples = 0
        climate_fine_tiles = 0
        if surface_ctx is not None:
            climate_result, climate_coarse_samples = self._climate.bake_coarse(
                world, surface_ctx, writer,
            )
            writer.write_locations_index(build_locations_index(locations))

        world_map_cells = self._world_map.bake_tiles(
            world, locations, writer, tiles,
            surface_ctx=surface_ctx,
            nodes=nodes, edges=edges, hydrology_generator=hydrology_generator,
        )
        terrain_result = PersistResult.from_counts(world_map_cells, world_map_cells)
        chunks_done = 0
        chunks_total = 0

        if refine_scene and tiles and surface_ctx is not None:
            ax = anchor_x
            ay = anchor_y
            if ax is None or ay is None:
                for loc in locations:
                    if loc.map_x is not None and loc.map_y is not None:
                        ax = loc.map_x
                        ay = loc.map_y
                        break
            ax = ax if ax is not None else 0
            ay = ay if ay is not None else 0
            tile_gx, tile_gy = self._fine_terrain.tile_for_anchor(world, ax, ay)
            self._anchors.set_anchor("session_start", ax, ay, tile_gx=tile_gx, tile_gy=tile_gy)
            heading = resolve_path_heading(
                intent_dx=heading_dx,
                intent_dy=heading_dy,
                positions=self._anchors.position_history(),
            )
            terrain_result, chunks_done, chunks_total = await self._fine_terrain.refine_scene_volume(
                world, locations, writer, ax, ay, mat_ctx,
                surface_ctx=surface_ctx, tile_gx=tile_gx, tile_gy=tile_gy,
                xy_radius=SceneVolumePolicy.canonical_defaults().scene_xy_radius,
            )
            self._climate_fine.enqueue(tile_gx, tile_gy)
            path_chunks = await self._fine_terrain.refine_path_corridor(
                world, locations, writer, ax, ay, mat_ctx, surface_ctx,
                tile_gx, tile_gy,
                heading=heading,
                depth_tiles=app_settings.path_ahead_depth,
            )
            chunks_done += path_chunks
            await self._fine_terrain.schedule_tile_background(
                world, self._queue, ax, ay, tile_gx, tile_gy,
            )
            if heading is not None:
                await self._fine_terrain.schedule_path_ahead_tiles(
                    world, self._queue, ax, ay, tile_gx, tile_gy, heading,
                    depth_tiles=app_settings.path_ahead_depth,
                )
            for gx, gy, cx, cy, priority in self._queue.pending_items():
                log_pack_queue_enqueue(world_uid, gx, gy, cx, cy, priority=priority)
                await self._worker.persist_enqueue(
                    world_uid, gx, gy, cx, cy, priority=priority,
                )
            log_pack_jobs_persisted(world_uid, count=len(self._queue))
            if self._defaults.background_drain_per_request > 0:
                _drained_chunks, fine_tiles = await self._worker.drain_queue(
                    world_uid, world, locations, writer, mat_ctx, surface_ctx,
                    self._queue, max_jobs=self._defaults.background_drain_per_request,
                )
                climate_fine_tiles += fine_tiles
            else:
                # Terrain drain skipped — still bake enqueued fine climate (spawn tile).
                climate_fine_tiles += self._worker.drain_climate_fine(
                    world, surface_ctx, writer,
                )
            if climate_result is not None and climate_fine_tiles:
                climate_result = PersistResult.from_counts(
                    climate_result.total + climate_fine_tiles,
                    climate_result.succeeded + climate_fine_tiles,
                )
            elif climate_fine_tiles and climate_result is None:
                climate_result = PersistResult.from_counts(climate_fine_tiles, climate_fine_tiles)

        if self._world_service is not None:
            await finalize_pack_on_world(self._world_service, world, writer)

        workers = resolve_terrain_workers(mat_ctx, world)
        elapsed_s = time.perf_counter() - bake_t0
        log_pack_bake_done(
            world_uid,
            world_map_cells=world_map_cells,
            chunks_done=chunks_done,
            chunks_total=chunks_total,
            queue_depth=len(self._queue),
            started_at=bake_t0,
        )
        return MaterializationJobReport(
            terrain=terrain_result,
            climate=climate_result,
            chunks_done=chunks_done,
            chunks_total=chunks_total,
            terrain_workers=workers,
            climate_workers=0,
            elapsed_s=elapsed_s,
            world_map_cells=world_map_cells,
            refine_queue_depth=len(self._queue),
            climate_coarse_samples=climate_coarse_samples or None,
            climate_fine_tiles=climate_fine_tiles or None,
        )
