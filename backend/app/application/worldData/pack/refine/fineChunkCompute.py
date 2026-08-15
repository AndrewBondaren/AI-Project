"""One ColumnRect worker: stamp planned grade then column fill (C28)."""

from __future__ import annotations

from dataclasses import replace

from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.application.worldData.pack.bake.packBakeLog import log_pack_wilderness_chunk_start
from app.application.worldData.pack.refine.columnBounds import rect_contains
from app.application.worldData.pack.refine.detailedGradeGenerate import (
    materialize_planned_for_rect,
)
from app.application.worldData.pack.refine.fineTileContext import (
    ChunkComputeResult,
    FineTileContext,
)
from app.application.worldData.pack.refine.meterGradeSurface import Coord
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.terrain.relief.reliefGradeInstance import ReliefGradeInstance


def rect_heightmap_from_overlay(
    heightmap: SurfaceHeightmap,
    overlay: dict[Coord, int],
    rect: ColumnRect,
) -> SurfaceHeightmap:
    """Rect-local z for fill: parent ⊕ overlay. New dict — shared heightmap untouched."""
    parent = heightmap.surface_z
    local = {
        xy: overlay[xy] if xy in overlay else z
        for xy, z in parent.items()
        if rect_contains(rect, xy[0], xy[1])
    }
    return SurfaceHeightmap(
        world_uid=heightmap.world_uid,
        bbox=heightmap.bbox,
        surface_z=local,
    )


def compute_rect(
    terrain: TerrainBatchOrchestrator,
    ctx: FineTileContext,
    pair: tuple[int, ColumnRect],
) -> ChunkComputeResult:
    """Stamp + fill one ColumnRect. Sample/stitch already on ``ctx.planned`` (C28)."""
    chunk_idx, rect = pair
    chunk_t0 = log_pack_wilderness_chunk_start(
        ctx.world_uid,
        phase=ctx.phase_name,
        tile_gx=ctx.tile_gx,
        tile_gy=ctx.tile_gy,
        chunk_idx=chunk_idx,
        chunks_total=ctx.chunks_total,
        rect=rect,
        refine_role=ctx.refine_role,
        pool_workers=ctx.workers,
    )
    chunk_grades: tuple[ReliefGradeInstance, ...] = ()
    chunk_state = ctx.surface_state
    if ctx.templates:
        if ctx.planned is None:
            raise ValueError(
                "FineTileContext.templates set but planned is None "
                "(sample/stitch must run before compute_rect)"
            )
        if ctx.planned:
            part = materialize_planned_for_rect(
                ctx.world, ctx.surface_state, rect, list(ctx.planned),
                existing_uids=ctx.existing_uids,
                catalog=ctx.catalog,
            )
            chunk_grades = part.grade_instances
            local_hm = rect_heightmap_from_overlay(
                ctx.surface_state.heightmap, part.surface_z, rect,
            )
            chunk_state = replace(
                ctx.surface_state,
                heightmap=local_hm,
                surface_grade_uid=part.surface_grade_uid,
            )
    cells = terrain.generate_chunk_cells_sync(
        ctx.world, ctx.locations, ctx.surface_ctx, ctx.tile_gx, ctx.tile_gy, rect,
        surface_state=chunk_state,
    )
    return ChunkComputeResult(
        chunk_idx=chunk_idx,
        rect=rect,
        cells=cells,
        chunk_t0=chunk_t0,
        chunk_grades=chunk_grades,
    )
