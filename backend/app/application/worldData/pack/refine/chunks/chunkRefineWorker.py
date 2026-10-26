"""Background chunk refine worker — WP-11/12 + climate fine drain (CL-PACK-2)."""

from __future__ import annotations
from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps

from collections.abc import Mapping

from app.application.worldData.generators.terrain.landcover.types import StateSnapshotEntry
from app.ids import runtime_uid
from app.application.worldData.materialize.surface.materializationContext import MaterializationContext
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.pack.refine.chunks.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.climate.climateFinePending import ClimateFinePending
from app.application.worldData.pack.climate.climatePackBakeOrchestrator import ClimatePackBakeOrchestrator
from app.application.worldData.pack.refine.fine.fineRectRefiner import FineRectRefiner
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_drain_queue_done,
    log_pack_drain_queue_start,
    log_pack_worker_chunk,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.dataModel.worldPack.bake.gradePipelineStages import GradePipelineStages
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.db.repositories.iChunkRefineJobRepository import IChunkRefineJobRepository
from app.db.repositories.sqlite.chunkRefineJobRepository import new_chunk_refine_job


class ChunkRefineWorker:
    def __init__(
        self,
        rect_refiner: FineRectRefiner,
        *,
        job_repo: IChunkRefineJobRepository | None = None,
        climate_bake: ClimatePackBakeOrchestrator | None = None,
        climate_fine: ClimateFinePending | None = None,
    ) -> None:
        self._rect_refiner = rect_refiner
        self._jobs = job_repo
        self._climate = climate_bake
        self._climate_fine = climate_fine

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
            new_chunk_refine_job(
                world_uid, gx, gy, cx, cy,
                job_uid=runtime_uid(), priority=priority,
            ),
        )

    async def drain_climate_fine(
        self,
        world: World,
        surface_bundle: SurfacePlanBundle | None,
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        max_tiles: int = 0,
        working: SurfaceWorkingMaps,
    ) -> int:
        """Bake pending fine climate tiles. max_tiles<=0 means all pending."""
        if self._climate is None or self._climate_fine is None or surface_bundle is None:
            return 0
        baked = 0
        while True:
            if max_tiles > 0 and baked >= max_tiles:
                break
            nxt = self._climate_fine.pop_next()
            if nxt is None:
                break
            gx, gy = nxt
            if await self._climate.bake_fine_tile_with_parent(
                world, surface_bundle, writer, mat_ctx, gx, gy, require_parent=True,
                working=working,
            ):
                baked += 1
        return baked

    async def drain_queue(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_bundle: SurfacePlanBundle,
        queue: ChunkRefineQueue,
        *,
        max_jobs: int = 0,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> tuple[int, int]:
        drain_t0 = log_pack_drain_queue_start(world_uid, max_jobs=max_jobs, pending=len(queue))
        processed = 0
        while True:
            if max_jobs > 0 and processed >= max_jobs:
                break
            nxt = queue.pop_next()
            if nxt is None:
                break
            gx, gy, cx, cy = nxt
            result = await self._rect_refiner.refine_queued_chunk(
                world, locations, writer, mat_ctx, surface_bundle,
                gx, gy, cx, cy,
                stages=GradePipelineStages.off(),
                region_state_snapshot=region_state_snapshot,
                working=working,
            )
            processed += 1
            log_pack_worker_chunk(
                world_uid,
                activity="drain_queue_chunk",
                tile_gx=gx,
                tile_gy=gy,
                chunk_cx=cx,
                chunk_cy=cy,
                cells=result.persist.succeeded,
            )
        fine_tiles = await self.drain_climate_fine(world, surface_bundle, writer, mat_ctx, working=working)
        log_pack_drain_queue_done(world_uid, processed=processed, started_at=drain_t0)
        return processed, fine_tiles

    async def drain_persisted(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_bundle: SurfacePlanBundle,
        *,
        max_jobs: int = 1,
        region_state_snapshot: Mapping[str, StateSnapshotEntry],
        working: SurfaceWorkingMaps,
    ) -> int:
        if self._jobs is None or max_jobs <= 0:
            fine = await self.drain_climate_fine(world, surface_bundle, writer, mat_ctx, working=working)
            return fine
        processed = 0
        while processed < max_jobs:
            job = await self._jobs.pop_next_pending(world_uid)
            if job is None:
                break
            result = await self._rect_refiner.refine_queued_chunk(
                world, locations, writer, mat_ctx, surface_bundle,
                job.gx, job.gy, job.cx, job.cy,
                stages=GradePipelineStages.off(),
                region_state_snapshot=region_state_snapshot,
                working=working,
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
                cells=result.persist.succeeded,
                job=job.job_uid,
            )
        processed += await self.drain_climate_fine(world, surface_bundle, writer, mat_ctx, working=working)
        return processed
