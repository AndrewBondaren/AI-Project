"""L2 fine-chunk generate + pack persist — WP-PERF-22 parent light path.

Owns pool dispatch. Prep / compute / persist live in sibling modules.
Does not enqueue background jobs (see ``chunkSchedule``).
"""

from __future__ import annotations

import time
from dataclasses import replace
from functools import partial

from app.application.worldData.chunkComputePool import ChunkComputePool
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.packBakeLog import log_pack_l2_formation_done
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.refine.fineChunkCompute import compute_rect
from app.application.worldData.pack.refine.fineChunkPersist import FineChunkPersist
from app.application.worldData.pack.refine.fineGradeCatalog import emit_fine_grade_catalog
from app.application.worldData.pack.refine.fineRefineResult import FineRefineResult
from app.application.worldData.pack.refine.fineTileContext import ChunkComputeResult
from app.application.worldData.pack.refine.fineTilePrep import prepare_fine_tile
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.gradePipelineStages import GradePipelineStages
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class FineChunkRunner:
    """Parent light → surface → chunk generate → pack persist."""

    def __init__(self, terrain: TerrainBatchOrchestrator) -> None:
        self._terrain = terrain

    async def refine_rects(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        rects: list[ColumnRect],
        volumes: list[TerritoryVolume],
        *,
        refine_role: ChunkRefineRole = "scene",
        phase: str | None = None,
        relief_templates_by_uid: dict[str, ReliefTemplate] | None = None,
        stages: GradePipelineStages | None = None,
    ) -> FineRefineResult:
        """Generate + persist fine chunks; ``meter_surface_z`` for climate ladder."""
        if not rects:
            return FineRefineResult.empty()

        l2_t0 = time.perf_counter()
        ctx = prepare_fine_tile(
            self._terrain,
            world,
            locations,
            writer,
            mat_ctx,
            surface_ctx,
            tile_gx,
            tile_gy,
            rects,
            volumes,
            refine_role=refine_role,
            phase=phase,
            relief_templates_by_uid=relief_templates_by_uid,
            stages=stages or GradePipelineStages.off(),
        )
        persist = FineChunkPersist(ctx, writer)
        compute = partial(compute_rect, self._terrain, ctx)
        indexed_rects = list(enumerate(rects, start=1))

        if ctx.workers == 1 or ctx.chunks_total <= 1:
            for pair in indexed_rects:
                persist.persist_rect(compute(pair))
        else:
            pool = ChunkComputePool(
                ctx.workers,
                thread_name_prefix="pack-compute",
                log_diagnostics=True,
            )
            try:
                async def on_chunk(
                    _pair: tuple[int, ColumnRect],
                    result: ChunkComputeResult,
                ) -> None:
                    await persist.persist_rect_locked(result)

                await pool.map_sync_with_callback(indexed_rects, compute, on_chunk)
            finally:
                pool.shutdown()

        pack = persist.finish()
        instances, systems, emit_s = emit_fine_grade_catalog(
            pack.grade_instances,
            pack.vertex_seams,
            ctx.catalog,
            world_uid=ctx.world_uid,
        )
        result = replace(
            pack,
            grade_instances=instances,
            grade_systems=systems,
            pipeline_s=replace(pack.pipeline_s, systems_emit_s=emit_s),
        )
        log_pack_l2_formation_done(
            ctx.world_uid,
            phase=ctx.phase_name,
            chunks=ctx.chunks_total,
            materialize_s=result.materialize_s,
            grade_s=result.grade_s,
            l2_s=time.perf_counter() - l2_t0,
            tile_gx=ctx.tile_gx,
            tile_gy=ctx.tile_gy,
            workers=ctx.workers,
            pipeline=result.pipeline_s,
        )
        return result
