"""L2 fine-chunk generate + pack persist — WP-PERF-22 parent light path.

Owns pool dispatch. Prep / compute / persist live in sibling modules.
Does not enqueue background jobs (see ``chunkSchedule``).
"""

from __future__ import annotations

from dataclasses import replace
from functools import partial

from app.application.worldData.chunkComputePool import ChunkComputePool
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.refine.fineChunkCompute import compute_rect
from app.application.worldData.pack.refine.fineChunkPersist import FineChunkPersist
from app.application.worldData.pack.refine.fineRefineResult import FineRefineResult
from app.application.worldData.pack.refine.fineTileContext import ChunkComputeResult
from app.application.worldData.pack.refine.fineTilePrep import prepare_fine_tile
from app.application.worldData.pack.refine.detailedGradeGenerate import plan_grade_for_rects
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
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
    ) -> FineRefineResult:
        """Generate + persist fine chunks; ``meter_surface_z`` for climate ladder."""
        if not rects:
            return FineRefineResult.empty()

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
        )
        if ctx.templates:
            planned = plan_grade_for_rects(
                ctx.world,
                ctx.surface_state,
                rects,
                catalog=ctx.catalog,
                relief_templates_by_uid=ctx.templates,
                existing_uids=ctx.existing_uids,
            )
            ctx = replace(ctx, planned=tuple(planned))
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

        return persist.finish()
