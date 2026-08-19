"""One ColumnRect worker: discover+paint then one column fill (R41 / C28).

Discover on the ready heightmap, then one fill.
Plan: ``.cursor/plans/relief-pipeline-v2.md``.
"""

from __future__ import annotations

import time
from dataclasses import replace

from app.application.worldData.generators.terrain.types import ColumnRect, SurfaceHeightmap
from app.application.worldData.pack.bake.packBakeLog import log_pack_wilderness_chunk_start
from app.application.worldData.pack.refine.columnBounds import rect_contains
from app.application.worldData.pack.refine.detailedGradeDiscover import discover_and_paint
from app.application.worldData.pack.refine.fineTileContext import (
    ChunkComputeResult,
    FineTileContext,
    VertexSlotSeam,
)
from app.application.worldData.pack.refine.meterGradeSurface import Coord
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator


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
    """Discover+paint on the ready heightmap, then one fill (R41)."""
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
    chunk_grades: tuple = ()
    vertex_seams: tuple[VertexSlotSeam, ...] = ()
    rim_rays: tuple = ()
    chunk_state = ctx.surface_state
    grade_s = 0.0
    if ctx.templates:
        grade_t0 = time.perf_counter()
        part, vertex_seams = discover_and_paint(
            ctx.world,
            ctx.surface_state,
            rect,
            halo=ctx.grade_halo,
            catalog=ctx.catalog,
            templates=ctx.templates,
            existing_uids=ctx.existing_uids,
        )
        grade_s = time.perf_counter() - grade_t0
        chunk_grades = part.grade_instances
        rim_rays = part.rim_rays
        if part.surface_z or part.surface_grade_uid:
            local_hm = rect_heightmap_from_overlay(
                ctx.surface_state.heightmap, part.surface_z, rect,
            )
            chunk_state = replace(
                ctx.surface_state,
                heightmap=local_hm,
                surface_grade_uid=part.surface_grade_uid,
            )
    mat_t0 = time.perf_counter()
    cells = terrain.generate_chunk_cells_sync(
        ctx.world, ctx.locations, ctx.surface_ctx, ctx.tile_gx, ctx.tile_gy, rect,
        surface_state=chunk_state,
    )
    materialize_s = time.perf_counter() - mat_t0
    return ChunkComputeResult(
        chunk_idx=chunk_idx,
        rect=rect,
        cells=cells,
        chunk_t0=chunk_t0,
        chunk_grades=chunk_grades,
        vertex_seams=vertex_seams,
        rim_rays=rim_rays,
        materialize_s=materialize_s,
        grade_s=grade_s,
    )
