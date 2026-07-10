"""Background chunk refine worker — WP-11/12."""

from __future__ import annotations

import logging

from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.l2RefineOrchestrator import L2RefineOrchestrator
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.db.repositories.sqlite.chunkRefineJobRepository import new_chunk_refine_job

logger = logging.getLogger(__name__)


class ChunkRefineWorker:
    def __init__(
        self,
        l2: L2RefineOrchestrator,
        *,
        job_repo: IChunkRefineJobRepository | None = None,
    ) -> None:
        self._l2 = l2
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
        processed = 0
        while True:
            if max_jobs > 0 and processed >= max_jobs:
                break
            nxt = queue.pop_next()
            if nxt is None:
                break
            gx, gy, cx, cy = nxt
            cells = await self._l2.refine_queued_chunk(
                world, locations, writer, mat_ctx, surface_ctx,
                gx, gy, cx, cy,
            )
            processed += 1
            logger.info(
                "chunk_refine_worker | world=%s tile=%d,%d chunk=%d,%d cells=%d",
                world_uid, gx, gy, cx, cy, cells,
            )
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
            cells = await self._l2.refine_queued_chunk(
                world, locations, writer, mat_ctx, surface_ctx,
                job.gx, job.gy, job.cx, job.cy,
            )
            await self._jobs.mark_complete(job.job_uid)
            processed += 1
            logger.info(
                "chunk_refine_persisted | job=%s world=%s cells=%d",
                job.job_uid, world_uid, cells,
            )
        return processed
