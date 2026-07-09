"""Terrain skeleton materialization — coarse/fine surface + hydrology planning.

Symmetry with ``ClimateBatchOrchestrator``: generators stay pure; persist via
``MapCellService.save_pass``. Debug routes and future DAG nodes call this facade.

See ``docs/tz_terrain_generation.md`` § multi-pass skeleton, MR-7, TR-PAR.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Literal

from app.api.schemas.imports import ImportResult
from app.application.worldData.chunkComputePool import ChunkComputePool
from app.application.worldData.generators.assemblers.climateAssembler.passes.poleResolvePass import (
    run_pole_resolve_pass,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.passes.gapAnalysisPass import run_gap_analysis
from app.application.worldData.generators.terrain.terrainGeneratorService import TerrainGeneratorService
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    force_serial_terrain_generate,
    terrain_chunk_columns,
)
from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.parallelPolicy import resolve_terrain_workers
from app.application.worldData.terrainParallelLog import (
    log_terrain_chunk_generate_done,
    log_terrain_chunk_generate_start,
    log_terrain_chunk_persist,
    log_terrain_tile_start,
)
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

if TYPE_CHECKING:
    from app.application.worldData.bootstrapMapCellWriter import BootstrapMapCellWriter

logger = logging.getLogger(__name__)

SurfaceMode = Literal["bootstrap", "full"]


class TerrainBatchOrchestrator:
    """Coarse plan → bootstrap tiles → fine column fill → terrain persist."""

    def __init__(
        self,
        map_cell_service: MapCellService,
        generator: TerrainGeneratorService | None = None,
    ) -> None:
        self._map_cells = map_cell_service
        self._generator = generator or TerrainGeneratorService()

    def plan_bootstrap_tiles(
        self,
        world: World,
        locations: list[NamedLocation],
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        max_tiles: int | None = 16,
    ) -> list[tuple[int, int]]:
        from app.application.worldData.generators.terrain.passes.bootstrapMacroTiles import (
            bootstrap_macro_tiles,
        )
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            prepare_surface_terrain_context,
        )

        ctx = prepare_surface_terrain_context(
            world,
            locations,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if ctx is None:
            return []
        return bootstrap_macro_tiles(
            world,
            locations,
            ctx.coarse_hydro,
            ctx.sparse_meter_hydro,
            max_tiles=max_tiles,
        )

    async def save_terrain_batch(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        ctx: MaterializationContext,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
        surface_mode: SurfaceMode = "bootstrap",
        max_tiles: int | None = 16,
        bootstrap_writer: BootstrapMapCellWriter | None = None,
    ) -> tuple[ImportResult, int, int]:
        from app.application.worldData.generators.coordinates import cell_size_m, iter_macro_tiles
        from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
        from app.application.worldData.generators.terrain.passes.bootstrapMacroTiles import (
            bootstrap_macro_tiles,
        )
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            prepare_surface_terrain_context,
        )

        macro_bbox = grid_bbox_from_locations(world, locations)
        if macro_bbox is None:
            return ImportResult(total=0, succeeded=0, failed=0), 0, 0

        surface_ctx = prepare_surface_terrain_context(
            world,
            locations,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if surface_ctx is None:
            return ImportResult(total=0, succeeded=0, failed=0), 0, 0

        cell_m = cell_size_m(world)
        if surface_mode == "full":
            tiles = list(iter_macro_tiles(macro_bbox))
        else:
            tiles = bootstrap_macro_tiles(
                world,
                locations,
                surface_ctx.coarse_hydro,
                surface_ctx.sparse_meter_hydro,
                max_tiles=max_tiles,
            )

        total = 0
        succeeded = 0
        chunks_done = 0
        chunks_total = 0
        for tile_gx, tile_gy in tiles:
            tile_result, tile_chunks_done, tile_chunks_total = await self._materialize_fine_tile(
                world, locations, surface_ctx, tile_gx, tile_gy, ctx,
                bootstrap_writer=bootstrap_writer,
            )
            total += tile_result.total
            succeeded += tile_result.succeeded
            chunks_done += tile_chunks_done
            chunks_total += tile_chunks_total

        logger.info(
            "save_terrain_batch | world=%s mode=%s fine tiles=%d cells=%d upserted=%d "
            "chunks=%d/%d workers=%d cell_m=%d",
            world_uid,
            surface_mode,
            len(tiles),
            total,
            succeeded,
            chunks_done,
            chunks_total,
            resolve_terrain_workers(ctx, world),
            cell_m,
        )
        return ImportResult(total=total, succeeded=succeeded, failed=0), chunks_done, chunks_total

    async def materialize_macro_tile(
        self,
        world_uid: str,
        world: World,
        locations: list[NamedLocation],
        tile_gx: int,
        tile_gy: int,
        ctx: MaterializationContext,
        *,
        nodes: list[ConnectionNode] | None = None,
        edges: list[ConnectionEdge] | None = None,
        hydrology_generator: HydrologyGeneratorService | None = None,
    ) -> tuple[ImportResult, int, int]:
        """Fine grid for one macro tile (map_cell_size_m² × subsurface columns)."""
        from app.application.worldData.generators.terrain.passes.bbox import grid_bbox_from_locations
        from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
            prepare_surface_terrain_context,
        )

        if grid_bbox_from_locations(world, locations) is None:
            return ImportResult(total=0, succeeded=0, failed=0), 0, 0

        surface_ctx = prepare_surface_terrain_context(
            world,
            locations,
            nodes=nodes,
            edges=edges,
            hydrology_generator=hydrology_generator,
        )
        if surface_ctx is None:
            return ImportResult(total=0, succeeded=0, failed=0), 0, 0

        result, chunks_done, chunks_total = await self._materialize_fine_tile(
            world, locations, surface_ctx, tile_gx, tile_gy, ctx,
        )
        logger.info(
            "materialize_macro_tile | world=%s tile=(%d,%d) cells=%d upserted=%d chunks=%d/%d",
            world_uid, tile_gx, tile_gy, result.total, result.succeeded,
            chunks_done, chunks_total,
        )
        return result, chunks_done, chunks_total

    async def save_z_slice(
        self,
        world: World,
        locations: list[NamedLocation],
        gx: int,
        gy: int,
        z_lo: int,
        z_hi: int,
    ) -> ImportResult:
        pole_field = run_pole_resolve_pass(world, locations)
        cells = self._generator.generate_z_slice(
            world, locations, pole_field, gx, gy, z_lo, z_hi,
        )
        return await self._map_cells.save_pass(cells, "terrain")

    async def _persist_chunk_batch(
        self,
        world_uid: str,
        workers: int,
        chunks_total: int,
        batch: list[tuple[int, ColumnRect, list[MapCell]]],
        *,
        insert_only: bool = False,
        bootstrap_writer: BootstrapMapCellWriter | None = None,
    ) -> tuple[int, int]:
        """TR-PERF-2: one transaction for up to chunks_per_commit terrain chunks."""
        if not batch:
            return 0, 0
        if bootstrap_writer is not None:
            chunk_lists = [chunk_cells for _, _, chunk_cells in batch]
            total = sum(len(cells) for cells in chunk_lists)
            t_persist = time.perf_counter()
            succeeded = await bootstrap_writer.write_terrain_chunk_batch(
                chunk_lists, insert_only=insert_only,
            )
            elapsed_ms = (time.perf_counter() - t_persist) * 1000.0
            for chunk_idx, rect, chunk_cells in batch:
                log_terrain_chunk_persist(
                    world_uid, chunk_idx, chunks_total,
                    workers=workers, rect=rect, cell_count=len(chunk_cells),
                    upserted=len(chunk_cells),
                    elapsed_ms=elapsed_ms / len(batch),
                )
            return total, succeeded

        total = 0
        succeeded = 0
        async with self._map_cells.bulk_persist_session():
            for chunk_idx, rect, chunk_cells in batch:
                total += len(chunk_cells)
                t_persist = time.perf_counter()
                result = await self._map_cells.save_pass(
                    chunk_cells, "terrain", insert_only=insert_only,
                )
                log_terrain_chunk_persist(
                    world_uid, chunk_idx, chunks_total,
                    workers=workers, rect=rect, cell_count=len(chunk_cells),
                    upserted=result.succeeded,
                    elapsed_ms=(time.perf_counter() - t_persist) * 1000.0,
                )
                succeeded += result.succeeded
        return total, succeeded

    async def _materialize_fine_tile(
        self,
        world: World,
        locations: list[NamedLocation],
        ctx,
        tile_gx: int,
        tile_gy: int,
        mat_ctx: MaterializationContext,
        *,
        bootstrap_writer: BootstrapMapCellWriter | None = None,
    ) -> tuple[ImportResult, int, int]:
        from app.application.worldData.generators.coordinates import cell_size_m
        from app.application.worldData.generators.coordinates.worldTile import (
            iter_meter_chunks,
            meter_bbox_for_tile,
        )
        from app.application.worldData.generators.terrain.hydrology.meterHydrologyIndex import (
            merge_meter_hydro_for_tile,
        )
        from app.application.worldData.generators.terrain.passes.surfacePass import build_fine_surface_tile
        from app.application.worldData.generators.terrain.types import SurfaceHeightmap

        cell_m = cell_size_m(world)
        fine_z = build_fine_surface_tile(
            world, ctx.pole_field, tile_gx, tile_gy, ctx.coarse_surface_z,
        )
        for (xm, ym), z in ctx.meter_z_overrides.items():
            if xm // cell_m == tile_gx and ym // cell_m == tile_gy:
                fine_z[(xm, ym)] = z

        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        heightmap = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=meter_bbox,
            surface_z=fine_z,
        )
        tile_hydro = merge_meter_hydro_for_tile(
            tile_gx, tile_gy, cell_m, ctx.coarse_hydro, ctx.sparse_meter_hydro,
        )
        n_eff = run_gap_analysis(world, heightmap)
        chunk_size = terrain_chunk_columns(world)
        rects = list(iter_meter_chunks(meter_bbox, chunk_size))
        chunks_total = len(rects)

        surface_columns = (meter_bbox.x_max - meter_bbox.x_min + 1) * (
            meter_bbox.y_max - meter_bbox.y_min + 1
        )
        workers = resolve_terrain_workers(mat_ctx, world)
        if force_serial_terrain_generate(world, surface_columns):
            workers = 1

        hydrology = tile_hydro or None
        world_uid = world.world_uid

        log_terrain_tile_start(
            world_uid, tile_gx, tile_gy, workers=workers, chunks_total=chunks_total,
        )

        def compute_chunk(rect: ColumnRect) -> list[MapCell]:
            return self._generator.generate_surface_chunk(
                world,
                locations,
                heightmap,
                n_eff,
                rect,
                hydrology_by_cell=hydrology,
            )

        def compute_chunk_logged(chunk_idx: int, rect: ColumnRect) -> list[MapCell]:
            t0 = log_terrain_chunk_generate_start(
                world_uid, chunk_idx, chunks_total, workers=workers, rect=rect,
            )
            cells = compute_chunk(rect)
            log_terrain_chunk_generate_done(
                world_uid, chunk_idx, chunks_total,
                workers=workers, rect=rect, cell_count=len(cells), started_at=t0,
            )
            return cells

        total = 0
        succeeded = 0
        chunks_done = 0
        chunks_per_commit = max(1, mat_ctx.chunks_per_commit)
        insert_only = bool(mat_ctx.insert_only)
        persist_buffer: list[tuple[int, ColumnRect, list[MapCell]]] = []

        async def flush_persist_buffer() -> None:
            nonlocal total, succeeded, chunks_done, persist_buffer
            if not persist_buffer:
                return
            batch = persist_buffer
            persist_buffer = []
            batch_total, batch_ok = await self._persist_chunk_batch(
                world_uid, workers, chunks_total, batch,
                insert_only=insert_only,
                bootstrap_writer=bootstrap_writer,
            )
            total += batch_total
            succeeded += batch_ok
            chunks_done += len(batch)

        if workers == 1 or chunks_total <= 1:
            for chunk_idx, rect in enumerate(rects):
                chunk_cells = compute_chunk_logged(chunk_idx, rect)
                persist_buffer.append((chunk_idx, rect, chunk_cells))
                if len(persist_buffer) >= chunks_per_commit:
                    await flush_persist_buffer()
            await flush_persist_buffer()
        else:
            pool = ChunkComputePool(workers)
            persist_lock = asyncio.Lock()
            indexed_rects = list(enumerate(rects))

            def compute_indexed(pair: tuple[int, ColumnRect]) -> list[MapCell]:
                chunk_idx, rect = pair
                return compute_chunk_logged(chunk_idx, rect)

            async def on_chunk(pair: tuple[int, ColumnRect], chunk_cells: list[MapCell]) -> None:
                nonlocal persist_buffer
                chunk_idx, rect = pair
                async with persist_lock:
                    persist_buffer.append((chunk_idx, rect, chunk_cells))
                    if len(persist_buffer) >= chunks_per_commit:
                        await flush_persist_buffer()

            await pool.map_sync_with_callback(indexed_rects, compute_indexed, on_chunk)
            async with persist_lock:
                await flush_persist_buffer()

        return ImportResult(total=total, succeeded=succeeded, failed=0), chunks_done, chunks_total
