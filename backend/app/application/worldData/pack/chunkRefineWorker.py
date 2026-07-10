"""Background chunk refine worker — WP-11/12."""

from __future__ import annotations

from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.fineTerrainRefineOrchestrator import FineTerrainRefineOrchestrator
from app.application.worldData.pack.packBakeLog import (
    log_pack_drain_queue_done,
    log_pack_drain_queue_start,
    log_pack_worker_chunk,
)
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.db.repositories.sqlite.chunkRefineJobRepository import new_chunk_refine_job


class ChunkRefineWorker:
    def __init__(
        self,
        fine_terrain: FineTerrainRefineOrchestrator,
        *,
        job_repo: IChunkRefineJobRepository | None = None,
    ) -> None:
        self._fine_terrain = fine_terrain
        self._jobs = job_repo

    async def persist_enqueue(
        self,
        world_uid: str,
        gx: int,
        gy: int,
        cx: int,
        cy: int,
        *,
        priority: float,
    ) -> None:
        if self._jobs is None:
            return
        if await self._jobs.has_pending(world_uid, gx, gy, cx, cy):
            return
        await self._jobs.upsert(
            new_chunk_refine_job(world_uid, gx, gy, cx, cy, priority=priority),
        )

    async def drain_queue(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx,
        queue: ChunkRefineQueue,
        *,
        max_jobs: int = 0,
    ) -> int:
        drain_t0 = log_pack_drain_queue_start(world_uid, max_jobs=max_jobs, pending=len(queue))
        processed = 0
        while True:
            if max_jobs > 0 and processed >= max_jobs:
                break
            nxt = queue.pop_next()
            if nxt is None:
                break
            gx, gy, cx, cy = nxt
            cells = await self._fine_terrain.refine_queued_chunk(
                world, locations, writer, mat_ctx, surface_ctx,
                gx, gy, cx, cy,
            )
            processed += 1
            log_pack_worker_chunk(
                world_uid,
                activity="drain_queue_chunk",
                tile_gx=gx,
                tile_gy=gy,
                chunk_cx=cx,
                chunk_cy=cy,
                cells=cells,
            )
        log_pack_drain_queue_done(world_uid, processed=processed, started_at=drain_t0)
        return processed

    async def drain_persisted(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx,
        *,
        max_jobs: int = 1,
    ) -> int:
        if self._jobs is None or max_jobs <= 0:
            return 0
        processed = 0
        while processed < max_jobs:
            job = await self._jobs.pop_next_pending(world_uid)
            if job is None:
                break
            cells = await self._fine_terrain.refine_queued_chunk(
                world, locations, writer, mat_ctx, surface_ctx,
                job.gx, job.gy, job.cx, job.cy,
            )
            await self._jobs.mark_complete(job.job_uid)
            processed += 1
            log_pack_worker_chunk(
                world_uid,
                activity="drain_persisted_job",
                tile_gx=job.gx,
                tile_gy=job.gy,
                chunk_cx=job.cx,
                chunk_cy=job.cy,
                cells=cells,
                job=job.job_uid,
            )
        return processed
