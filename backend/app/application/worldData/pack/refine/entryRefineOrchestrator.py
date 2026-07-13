"""WP-13 entry refine session — anchors, blocking scene/path, background schedule."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.worldData.persistResult import PersistResult
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_drain_persisted_done,
    log_pack_drain_persisted_start,
    log_pack_jobs_persisted,
    log_pack_queue_enqueue,
)
from app.application.worldData.pack.climate.climateFinePending import ClimateFinePending
from app.application.worldData.pack.climate.climatePackBakeOrchestrator import ClimatePackBakeOrchestrator
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.refine.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.refine.chunkRefineWorker import ChunkRefineWorker
from app.application.worldData.pack.refine.entryAnchorTracker import (
    AnchorKind,
    EntryAnchor,
    EntryAnchorTracker,
)
from app.application.worldData.pack.refine.fineTerrainRefineOrchestrator import FineTerrainRefineOrchestrator
from app.application.worldData.pack.refine.pathHeading import PathHeading, resolve_path_heading
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.core.appSettings import app_settings
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository


@dataclass(frozen=True)
class RefineFromEntryResult:
    """Blocking entry refine: scene volume + path corridor (no background enqueue)."""

    terrain: PersistResult
    chunks_done: int
    chunks_total: int
    tile_gx: int
    tile_gy: int
    anchor: EntryAnchor
    heading: PathHeading | None


@dataclass(frozen=True)
class ScheduleChunkRefineResult:
    """Background rings + path-ahead jobs (WP-13 / WP-PERF-10)."""

    enqueued: int
    queue_depth: int
    climate_fine_tiles: int


class EntryRefineOrchestrator:
    """Gameplay/debug entry session: set anchor → blocking refine → optional schedule."""

    def __init__(
        self,
        fine_terrain: FineTerrainRefineOrchestrator,
        *,
        job_repo: IChunkRefineJobRepository | None = None,
        bake_defaults: PackBakeDefaults | None = None,
        climate_bake: ClimatePackBakeOrchestrator | None = None,
        read_context: PackReadContext | None = None,
    ) -> None:
        self._fine_terrain = fine_terrain
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()
        self._anchors = EntryAnchorTracker()
        self._queue = ChunkRefineQueue(max_workers=self._defaults.refine_queue_max_workers)
        self._climate_fine = ClimateFinePending()
        self._climate = climate_bake or ClimatePackBakeOrchestrator(read_context=read_context)
        self._jobs = job_repo
        self._worker = ChunkRefineWorker(
            self._fine_terrain,
            job_repo=job_repo,
            climate_bake=self._climate,
            climate_fine=self._climate_fine,
        )

    @property
    def refine_queue(self) -> ChunkRefineQueue:
        return self._queue

    @property
    def anchor_tracker(self) -> EntryAnchorTracker:
        return self._anchors

    @property
    def climate_bake(self) -> ClimatePackBakeOrchestrator:
        return self._climate

    @property
    def has_job_repo(self) -> bool:
        return self._jobs is not None

    def set_entry_anchor(
        self,
        world: World,
        kind: AnchorKind,
        entry_x: int,
        entry_y: int,
        *,
        tile_gx: int | None = None,
        tile_gy: int | None = None,
        location_uid: str | None = None,
    ) -> EntryAnchor:
        """Record spawn / tile_cross / location_entry (no refine)."""
        gx, gy = tile_gx, tile_gy
        if gx is None or gy is None:
            gx, gy = self._fine_terrain.tile_for_anchor(world, entry_x, entry_y)
        return self._anchors.set_anchor(
            kind, entry_x, entry_y,
            tile_gx=gx, tile_gy=gy, location_uid=location_uid,
        )

    def _resolve_heading(
        self,
        *,
        heading: PathHeading | None,
        heading_dx: int | None,
        heading_dy: int | None,
    ) -> PathHeading | None:
        if heading is not None:
            return heading
        return resolve_path_heading(
            intent_dx=heading_dx,
            intent_dy=heading_dy,
            positions=self._anchors.position_history(),
        )

    async def drain_persisted(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        *,
        max_jobs: int,
    ) -> int:
        drain_t0 = log_pack_drain_persisted_start(world_uid, max_jobs=max_jobs)
        drained = await self._worker.drain_persisted(
            world_uid, world, locations, writer, mat_ctx, surface_ctx,
            max_jobs=max_jobs,
        )
        log_pack_drain_persisted_done(world_uid, processed=drained, started_at=drain_t0)
        return drained

    async def refine_from_entry(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        *,
        kind: AnchorKind,
        anchor_x: int,
        anchor_y: int,
        location_uid: str | None = None,
        heading: PathHeading | None = None,
        heading_dx: int | None = None,
        heading_dy: int | None = None,
    ) -> RefineFromEntryResult:
        """Blocking only: set anchor, scene volume, path corridor (WP-13 P0)."""
        policy = SceneVolumePolicy.canonical_defaults()
        anchor = self.set_entry_anchor(
            world, kind, anchor_x, anchor_y, location_uid=location_uid,
        )
        if anchor.tile_gx is None or anchor.tile_gy is None:
            raise RuntimeError("set_entry_anchor must resolve tile_gx/tile_gy")
        tile_gx, tile_gy = anchor.tile_gx, anchor.tile_gy

        resolved_heading = self._resolve_heading(
            heading=heading, heading_dx=heading_dx, heading_dy=heading_dy,
        )

        terrain_result, chunks_done, chunks_total = await self._fine_terrain.refine_scene_volume(
            world, locations, writer, anchor_x, anchor_y, mat_ctx,
            surface_ctx=surface_ctx, tile_gx=tile_gx, tile_gy=tile_gy,
            xy_radius=policy.scene_xy_radius,
        )
        self._climate_fine.enqueue(tile_gx, tile_gy)

        path_chunks = await self._fine_terrain.refine_path_corridor(
            world, locations, writer, anchor_x, anchor_y, mat_ctx, surface_ctx,
            tile_gx, tile_gy,
            heading=resolved_heading,
            depth_tiles=app_settings.path_ahead_depth,
        )
        chunks_done += path_chunks

        return RefineFromEntryResult(
            terrain=terrain_result,
            chunks_done=chunks_done,
            chunks_total=chunks_total,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            anchor=anchor,
            heading=resolved_heading,
        )

    async def schedule_chunk_refine(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        *,
        anchor_x: int,
        anchor_y: int,
        tile_gx: int | None = None,
        tile_gy: int | None = None,
        heading: PathHeading | None = None,
        heading_dx: int | None = None,
        heading_dy: int | None = None,
    ) -> ScheduleChunkRefineResult:
        """Background only: rings from anchor + path-ahead neighbors, then persist jobs."""
        policy = SceneVolumePolicy.canonical_defaults()
        gx, gy = tile_gx, tile_gy
        if gx is None or gy is None:
            current = self._anchors.current
            if (
                current is not None
                and current.tile_gx is not None
                and current.tile_gy is not None
                and current.entry_x == anchor_x
                and current.entry_y == anchor_y
            ):
                gx, gy = current.tile_gx, current.tile_gy
            else:
                gx, gy = self._fine_terrain.tile_for_anchor(world, anchor_x, anchor_y)

        resolved_heading = self._resolve_heading(
            heading=heading, heading_dx=heading_dx, heading_dy=heading_dy,
        )

        before = len(self._queue)
        skip = self._fine_terrain.scene_chunk_indices(
            world, gx, gy, anchor_x, anchor_y,
            xy_radius=policy.scene_xy_radius,
        )
        await self._fine_terrain.schedule_tile_background(
            world, self._queue, anchor_x, anchor_y, gx, gy,
            skip_scene_rects=skip,
        )
        if resolved_heading is not None:
            await self._fine_terrain.schedule_path_ahead_tiles(
                world, self._queue, anchor_x, anchor_y, gx, gy,
                resolved_heading,
                depth_tiles=app_settings.path_ahead_depth,
            )
        enqueued = len(self._queue) - before

        for q_gx, q_gy, cx, cy, priority in self._queue.pending_items():
            log_pack_queue_enqueue(world_uid, q_gx, q_gy, cx, cy, priority=priority)
            await self._worker.persist_enqueue(
                world_uid, q_gx, q_gy, cx, cy, priority=priority,
            )
        log_pack_jobs_persisted(world_uid, count=len(self._queue))

        climate_fine_tiles = 0
        if self._defaults.background_drain_per_request > 0:
            _drained_chunks, fine_tiles = await self._worker.drain_queue(
                world_uid, world, locations, writer, mat_ctx, surface_ctx,
                self._queue, max_jobs=self._defaults.background_drain_per_request,
            )
            climate_fine_tiles += fine_tiles
        else:
            climate_fine_tiles += self._worker.drain_climate_fine(
                world, surface_ctx, writer,
            )

        return ScheduleChunkRefineResult(
            enqueued=enqueued,
            queue_depth=len(self._queue),
            climate_fine_tiles=climate_fine_tiles,
        )
