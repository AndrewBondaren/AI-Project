"""L2 fine-chunk generate + pack persist — WP-PERF-22 parent light path.

Owns pool, partition, wilderness / location_terrain writes. Does not enqueue
background jobs (see ``chunkSchedule``).
"""

from __future__ import annotations

import asyncio

from app.application.worldData.persistResult import PersistResult
from app.application.worldData.chunkComputePool import ChunkComputePool
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import meter_bbox_for_tile
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    force_serial_terrain_generate,
    terrain_chunk_columns,
)
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.parallelPolicy import resolve_terrain_workers
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_wilderness_chunk_done,
    log_pack_wilderness_chunk_persist,
    log_pack_wilderness_chunk_start,
    log_pack_location_terrain_persist,
    log_pack_fine_terrain_workers,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volumes_by_location,
)
from app.application.worldData.pack.read.mapCellToFineTerrainWire import (
    cells_to_fine_terrain_chunk,
)
from app.application.worldData.pack.refine.entryRingGeom import tile_local_chunk_indices
from app.application.worldData.pack.read.parentLightLoad import require_parent_light
from app.application.worldData.pack.refine.fineRefineResult import FineRefineResult
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.worldPack.territoryVolume import TerritoryVolume, inside_location_volume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def partition_chunk_cells(
    cells: list[MapCell],
    location_pairs: list[tuple[str, TerritoryVolume]],
    volumes: list[TerritoryVolume],
) -> tuple[list[MapCell], dict[str, list[MapCell]], set[str]]:
    wilderness: list[MapCell] = []
    location_additions: dict[str, list[MapCell]] = {}
    loc_hits: set[str] = set()
    for cell in cells:
        hit = location_for_cell(cell.x, cell.y, cell.z, location_pairs)
        if hit is not None:
            location_uid, _ = hit
            loc_hits.add(location_uid)
            location_additions.setdefault(location_uid, []).append(cell)
        elif not inside_location_volume(cell.x, cell.y, cell.z, volumes):
            wilderness.append(cell)
    return wilderness, location_additions, loc_hits


def location_for_cell(
    x: int,
    y: int,
    z: int,
    location_volumes: list[tuple[str, TerritoryVolume]],
) -> tuple[str, TerritoryVolume] | None:
    for location_uid, volume in location_volumes:
        if volume.contains(x, y, z):
            return location_uid, volume
    return None


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
    ) -> FineRefineResult:
        """Generate + persist fine chunks; ``meter_surface_z`` for climate ladder."""
        phase_name = phase or refine_role
        if not rects:
            return FineRefineResult.empty()

        chunk_size = terrain_chunk_columns(world)
        cell_m = cell_size_m(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        location_pairs = territory_volumes_by_location(world, locations)
        parent = require_parent_light(
            world.world_uid,
            tile_gx,
            tile_gy,
            reader=WorldPackReader(writer.paths),
            cache=writer.parent_light_cache,
            tile_m=cell_m,
        )
        surface_state = self._terrain.build_tile_surface_state(
            world, locations, surface_ctx, tile_gx, tile_gy, parent_light=parent,
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
        meter_surface_z: dict[tuple[int, int], int] = {}
        total_cells = 0
        written = 0
        world_uid = world.world_uid
        indexed_rects = list(enumerate(rects, start=1))
        write_lock = asyncio.Lock()

        def _note_surface_z(cells: list[MapCell]) -> None:
            for cell in cells:
                key = (int(cell.x), int(cell.y))
                prev = meter_surface_z.get(key)
                if prev is None or cell.z > prev:
                    meter_surface_z[key] = int(cell.z)

        def compute_indexed(
            pair: tuple[int, ColumnRect],
        ) -> tuple[int, ColumnRect, list[MapCell], float]:
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
            _note_surface_z(cells)
            wilderness, loc_additions, loc_hits = partition_chunk_cells(
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
                async def on_chunk(
                    _pair: tuple[int, ColumnRect],
                    result: tuple[int, ColumnRect, list[MapCell], float],
                ) -> None:
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
        return FineRefineResult(
            persist=PersistResult.from_counts(total_cells, total_cells),
            wilderness_chunks_written=written,
            rect_count=len(rects),
            meter_surface_z=meter_surface_z,
        )

