"""Wilderness chunk refine to pack — scene-volume blocking WP-13."""

from __future__ import annotations

import asyncio

from app.application.worldData.persistResult import PersistResult
from app.application.worldData.chunkComputePool import ChunkComputePool
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import iter_meter_chunks, meter_bbox_for_tile
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    force_serial_terrain_generate,
    terrain_chunk_columns,
)
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.parallelPolicy import resolve_terrain_workers
from app.application.worldData.pack.refine.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.refine.entryRingGeom import (
    chunk_within_ring,
    scene_chunk_indices as geom_scene_chunk_indices,
    tile_local_chunk_indices,
)
from app.application.worldData.pack.read.locationTerritoryVolumes import territory_volumes_by_location
from app.application.worldData.pack.read.mapCellToFineTerrainWire import cells_to_fine_terrain_chunk
from app.application.worldData.pack.read.packMapHelpers import tile_index, world_tile_size_m
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_wilderness_chunk_done,
    log_pack_wilderness_chunk_persist,
    log_pack_wilderness_chunk_start,
    log_pack_location_terrain_persist,
    log_pack_fine_terrain_phase_done,
    log_pack_fine_terrain_phase_start,
    log_pack_fine_terrain_workers,
    log_pack_queue_scheduled,
)
from app.application.worldData.pack.refine.pathHeading import (
    PathHeading,
    filter_corridor_rects,
    macro_tiles_ahead,
    predicted_border_entry,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.worldPack.pathHeadingPolicy import PathHeadingPolicy
from app.dataModel.worldPack.territoryVolume import TerritoryVolume, inside_location_volume
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _partition_chunk_cells(
    cells: list[MapCell],
    location_pairs: list[tuple[str, TerritoryVolume]],
    volumes: list[TerritoryVolume],
) -> tuple[list[MapCell], dict[str, list[MapCell]], set[str]]:
    wilderness: list[MapCell] = []
    location_additions: dict[str, list[MapCell]] = {}
    loc_hits: set[str] = set()
    for cell in cells:
        hit = _location_for_cell(cell.x, cell.y, cell.z, location_pairs)
        if hit is not None:
            location_uid, _ = hit
            loc_hits.add(location_uid)
            location_additions.setdefault(location_uid, []).append(cell)
        elif not inside_location_volume(cell.x, cell.y, cell.z, volumes):
            wilderness.append(cell)
    return wilderness, location_additions, loc_hits


def _location_for_cell(
    x: int,
    y: int,
    z: int,
    location_volumes: list[tuple[str, TerritoryVolume]],
) -> tuple[str, TerritoryVolume] | None:
    for location_uid, volume in location_volumes:
        if volume.contains(x, y, z):
            return location_uid, volume
    return None


class FineTerrainRefineOrchestrator:
    def __init__(self, terrain: TerrainBatchOrchestrator) -> None:
        self._terrain = terrain

    async def refine_scene_volume(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        anchor_x: int,
        anchor_y: int,
        mat_ctx: MaterializationContext,
        *,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        xy_radius: int,
        location_volumes: list[TerritoryVolume] | None = None,
    ) -> tuple[PersistResult, int, int]:
        loc_volumes = location_volumes or [vol for _, vol in territory_volumes_by_location(world, locations)]
        cell_m = cell_size_m(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        chunk_size = terrain_chunk_columns(world)
        rects = list(iter_meter_chunks(meter_bbox, chunk_size))
        scene_rects = [
            rect for rect in rects
            if chunk_within_ring(rect, float(anchor_x), float(anchor_y), float(xy_radius), chunk_size)
        ]
        phase_t0 = log_pack_fine_terrain_phase_start(
            world.world_uid,
            "scene",
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            rects=len(scene_rects),
        )
        result = await self._refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, scene_rects, loc_volumes,
            refine_role="scene",
            phase="scene",
        )
        log_pack_fine_terrain_phase_done(
            world.world_uid,
            "scene",
            chunks_written=result[1],
            cells_total=result[0].succeeded,
            started_at=phase_t0,
        )
        return result

    async def refine_rect(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        rect: ColumnRect,
        location_volumes: list[TerritoryVolume] | None = None,
        *,
        refine_role: str = "background",
    ) -> int:
        loc_volumes = location_volumes or [vol for _, vol in territory_volumes_by_location(world, locations)]
        result, _, _ = await self._refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, [rect], loc_volumes,
            refine_role=refine_role,  # type: ignore[arg-type]
            phase=refine_role,
        )
        return result.succeeded

    async def schedule_tile_background(
        self,
        world: World,
        queue: ChunkRefineQueue,
        anchor_x: int,
        anchor_y: int,
        tile_gx: int,
        tile_gy: int,
        *,
        skip_scene_rects: set[tuple[int, int]] | None = None,
        max_radius_m: float | None = None,
    ) -> int:
        """Enqueue background chunks near anchor — WP-13 rings, not whole tile (WP-PERF-10)."""
        from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy

        cell_m = cell_size_m(world)
        chunk_size = terrain_chunk_columns(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        skip = skip_scene_rects or set()
        policy = SceneVolumePolicy.canonical_defaults()
        radius = (
            float(max_radius_m)
            if max_radius_m is not None
            else float(policy.background_expand_radius_m)
        )
        count = 0
        for rect in iter_meter_chunks(meter_bbox, chunk_size):
            cx, cy = tile_local_chunk_indices(rect, meter_bbox, chunk_size)
            if (cx, cy) in skip:
                continue
            if not chunk_within_ring(rect, float(anchor_x), float(anchor_y), radius, chunk_size):
                continue
            if queue.enqueue_chunk(
                tile_gx, tile_gy, cx, cy,
                anchor_x=float(anchor_x),
                anchor_y=float(anchor_y),
                chunk_columns=chunk_size,
                tile_size_m=cell_m,
            ):
                count += 1
        if count:
            log_pack_queue_scheduled(
                world.world_uid,
                f"tile_background gx={tile_gx} gy={tile_gy} r<={radius:.0f}m",
                enqueued=count,
                queue_depth=len(queue),
            )
        return count

    def scene_chunk_indices(
        self,
        world: World,
        tile_gx: int,
        tile_gy: int,
        anchor_x: int,
        anchor_y: int,
        *,
        xy_radius: int | None = None,
    ) -> set[tuple[int, int]]:
        """Chunk (cx,cy) indices covered by scene volume around anchor."""
        from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy

        radius = (
            xy_radius
            if xy_radius is not None
            else SceneVolumePolicy.canonical_defaults().scene_xy_radius
        )
        return geom_scene_chunk_indices(
            world, tile_gx, tile_gy, anchor_x, anchor_y, xy_radius=radius,
        )

    async def schedule_path_ahead_tiles(
        self,
        world: World,
        queue: ChunkRefineQueue,
        anchor_x: int,
        anchor_y: int,
        tile_gx: int,
        tile_gy: int,
        heading: PathHeading,
        *,
        depth_tiles: int,
    ) -> int:
        """Enqueue background rings on macro-tiles ahead (WP-17).

        Each neighbor tile uses **predicted border entry** as ring anchor (WP-13),
        not the current spawn/session anchor.
        """
        tile_size = world_tile_size_m(world)
        count = 0
        prev_gx, prev_gy = tile_gx, tile_gy
        for ngx, ngy in macro_tiles_ahead(tile_gx, tile_gy, heading, depth_tiles):
            entry_x, entry_y = predicted_border_entry(
                prev_gx, prev_gy, ngx, ngy,
                float(anchor_x), float(anchor_y),
                tile_size,
            )
            count += await self.schedule_tile_background(
                world, queue, entry_x, entry_y, ngx, ngy,
            )
            prev_gx, prev_gy = ngx, ngy
        if count:
            log_pack_queue_scheduled(
                world.world_uid,
                f"path_ahead depth={depth_tiles}",
                enqueued=count,
                queue_depth=len(queue),
            )
        return count

    async def refine_queued_chunk(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        cx: int,
        cy: int,
    ) -> int:
        cell_m = cell_size_m(world)
        chunk_size = terrain_chunk_columns(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        x_min = meter_bbox.x_min + cx * chunk_size
        y_min = meter_bbox.y_min + cy * chunk_size
        rect = ColumnRect(
            x_min=x_min,
            x_max=x_min + chunk_size - 1,
            y_min=y_min,
            y_max=y_min + chunk_size - 1,
        )
        return await self.refine_rect(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, rect,
            refine_role="background",
        )

    async def _refine_rects(
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
        refine_role: str = "scene",
        phase: str | None = None,
    ) -> tuple[PersistResult, int, int]:
        phase_name = phase or refine_role
        if not rects:
            return PersistResult.from_counts(0, 0), 0, 0

        chunk_size = terrain_chunk_columns(world)
        cell_m = cell_size_m(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        location_pairs = territory_volumes_by_location(world, locations)
        surface_state = self._terrain.build_tile_surface_state(
            world, locations, surface_ctx, tile_gx, tile_gy,
        )
        surface_columns = (meter_bbox.x_max - meter_bbox.x_min + 1) * (
            meter_bbox.y_max - meter_bbox.y_min + 1
        )
        workers = resolve_terrain_workers(mat_ctx, world)
        if force_serial_terrain_generate(world, surface_columns):
            workers = 1
        chunks_total = len(rects)
        log_pack_fine_terrain_workers(
            world.world_uid,
            phase=phase_name,
            workers=workers,
            chunks_total=chunks_total,
        )

        location_cells: dict[str, list[MapCell]] = {}
        total_cells = 0
        written = 0
        world_uid = world.world_uid
        indexed_rects = list(enumerate(rects, start=1))
        write_lock = asyncio.Lock()

        def compute_indexed(pair: tuple[int, ColumnRect]) -> tuple[int, ColumnRect, list[MapCell], float]:
            chunk_idx, rect = pair
            chunk_t0 = log_pack_wilderness_chunk_start(
                world_uid,
                phase=phase_name,
                tile_gx=tile_gx,
                tile_gy=tile_gy,
                chunk_idx=chunk_idx,
                chunks_total=chunks_total,
                rect=rect,
                refine_role=refine_role,
                pool_workers=workers,
            )
            cells = self._terrain.generate_chunk_cells_sync(
                world, locations, surface_ctx, tile_gx, tile_gy, rect,
                surface_state=surface_state,
            )
            return chunk_idx, rect, cells, chunk_t0

        async def persist_chunk(
            chunk_idx: int,
            rect: ColumnRect,
            cells: list[MapCell],
            chunk_t0: float,
        ) -> None:
            nonlocal total_cells, written
            wilderness, loc_additions, loc_hits = _partition_chunk_cells(
                cells, location_pairs, volumes,
            )
            for location_uid, additions in loc_additions.items():
                location_cells.setdefault(location_uid, []).extend(additions)
            cx, cy = tile_local_chunk_indices(rect, meter_bbox, chunk_size)
            log_pack_wilderness_chunk_persist(
                world_uid,
                phase=phase_name,
                tile_gx=tile_gx,
                tile_gy=tile_gy,
                chunk_idx=chunk_idx,
                chunks_total=chunks_total,
                refine_role=refine_role,
                wilderness_cells=len(wilderness),
                location_uids=sorted(loc_hits),
                pool_workers=workers,
            )
            if wilderness:
                chunk = cells_to_fine_terrain_chunk(
                    cx, cy, chunk_size, rect.x_min, rect.y_min, wilderness,
                )
                writer.write_wilderness_chunk(
                    tile_gx, tile_gy, chunk,
                    refine_role=refine_role,  # type: ignore[arg-type]
                )
                total_cells += len(wilderness)
                written += 1
            log_pack_wilderness_chunk_done(
                world_uid,
                phase=phase_name,
                tile_gx=tile_gx,
                tile_gy=tile_gy,
                chunk_idx=chunk_idx,
                chunks_total=chunks_total,
                rect=rect,
                refine_role=refine_role,
                generated_cells=len(cells),
                wilderness_cells=len(wilderness),
                location_uids=sorted(loc_hits),
                started_at=chunk_t0,
                pool_workers=workers,
            )

        if workers == 1 or chunks_total <= 1:
            for pair in indexed_rects:
                chunk_idx, rect, cells, chunk_t0 = compute_indexed(pair)
                await persist_chunk(chunk_idx, rect, cells, chunk_t0)
        else:
            pool = ChunkComputePool(
                workers,
                thread_name_prefix="pack-compute",
                log_diagnostics=True,
            )
            try:
                async def on_chunk(_pair: tuple[int, ColumnRect], result: tuple[int, ColumnRect, list[MapCell], float]) -> None:
                    chunk_idx, rect, cells, chunk_t0 = result
                    async with write_lock:
                        await persist_chunk(chunk_idx, rect, cells, chunk_t0)

                await pool.map_sync_with_callback(indexed_rects, compute_indexed, on_chunk)
            finally:
                pool.shutdown()

        for location_uid, loc_cells in location_cells.items():
            volume = next((vol for uid, vol in location_pairs if uid == location_uid), None)
            if volume is None or not loc_cells:
                continue
            log_pack_location_terrain_persist(
                world_uid,
                location_uid=location_uid,
                cells=len(loc_cells),
                pool_workers=workers,
            )
            chunk = cells_to_fine_terrain_chunk(0, 0, chunk_size, volume.x0, volume.y0, loc_cells)
            writer.write_location_terrain(location_uid, chunk, territory_volume=volume)
            total_cells += len(loc_cells)
        writer.recalc_manifest_counters()
        writer.save_manifest()
        return PersistResult.from_counts(total_cells, total_cells), written, len(rects)

    async def refine_path_corridor(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        anchor_x: int,
        anchor_y: int,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        tile_gx: int,
        tile_gy: int,
        *,
        heading: PathHeading | None = None,
        depth_tiles: int = 2,
    ) -> int:
        """Refine coarse corridor ahead of anchor — PLAYER_PATH layer (MERGE-5 / DEBT-7)."""
        if heading is None or not heading.is_defined:
            return 0
        cell_m = cell_size_m(world)
        chunk_size = terrain_chunk_columns(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        rects = list(iter_meter_chunks(meter_bbox, chunk_size))
        depth_m = float(depth_tiles * cell_m)
        heading_policy = PathHeadingPolicy.canonical_defaults()
        corridor = filter_corridor_rects(
            rects,
            float(anchor_x),
            float(anchor_y),
            heading,
            depth_m=depth_m,
            half_width_m=heading_policy.corridor_half_width_m(chunk_size),
        )
        if not corridor:
            return 0
        loc_volumes = [vol for _, vol in territory_volumes_by_location(world, locations)]
        phase_t0 = log_pack_fine_terrain_phase_start(
            world.world_uid,
            "path",
            anchor_x=anchor_x,
            anchor_y=anchor_y,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            rects=len(corridor),
            heading=f"dx={heading.dx} dy={heading.dy}",
        )
        result, written, _ = await self._refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, corridor, loc_volumes,
            refine_role="path",
            phase="path",
        )
        log_pack_fine_terrain_phase_done(
            world.world_uid,
            "path",
            chunks_written=written,
            cells_total=result.succeeded,
            started_at=phase_t0,
        )
        return written

    @staticmethod
    def tile_for_anchor(world: World, anchor_x: int, anchor_y: int) -> tuple[int, int]:
        tile_size = world_tile_size_m(world)
        gx, _ = tile_index(anchor_x, tile_size)
        gy, _ = tile_index(anchor_y, tile_size)
        return gx, gy
