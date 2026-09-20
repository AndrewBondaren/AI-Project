"""Climate pack bake phases — coarse light + fine per-tile (CL-PACK-1 / CL-PAR)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar

from app.application.worldData.chunkComputePool import ChunkComputePool, split_contiguous_batches
from app.application.worldData.generators.coordinates import (
    grid_tile_origin_x,
    grid_tile_origin_y,
    map_cell_fine_span,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale
from app.application.worldData.pack.climate.climateCoarseBake import (
    build_climate_coarse_wire,
    build_climate_tile_wire,
    coarse_gy_rows,
    sample_climate_coarse_gy_rows,
    sample_climate_tile_ty_rows,
)
from app.application.worldData.pack.climate.climatePackSample import bucket_l2_z_by_light_cell
from app.application.worldData.pack.climate.lightFineTileResolve import (
    resolve_fine_tiles_for_policy,
)
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_climate_batch_done,
    log_pack_climate_batch_start,
    log_pack_climate_coarse_done,
    log_pack_climate_tile_done,
)
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.pack.read.parentLightLoad import load_parent_light
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.parallelPolicy import resolve_climate_workers
from app.application.worldData.persistResult import PersistResult
from app.dataModel.worldPack.climateFieldWire import ClimateSampleWire
from app.dataModel.worldPack.lightFineTilePolicy import LightFineTilePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.packTilePlan import PackTilePlanScope
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def _map_climate_row_batches(
    workers: int,
    rows: Sequence[T],
    compute_rows: Callable[[list[T]], list[ClimateSampleWire]],
    *,
    world_uid: str,
    phase: str,
    samples_per_row: int,
    tile_gx: int | None = None,
    tile_gy: int | None = None,
) -> list[ClimateSampleWire]:
    """Split *rows* across climate workers; persist stays on the caller."""
    batches = split_contiguous_batches(rows, workers)
    batches_total = len(batches)
    indexed = [(i + 1, batch) for i, batch in enumerate(batches)]

    def compute(item: tuple[int, list[T]]) -> list[ClimateSampleWire]:
        batch_idx, row_ids = item
        started = log_pack_climate_batch_start(
            world_uid,
            phase=phase,
            batch=batch_idx,
            batches_total=batches_total,
            workers=workers,
            samples=len(row_ids) * samples_per_row,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
        )
        samples = compute_rows(row_ids)
        log_pack_climate_batch_done(
            world_uid,
            phase=phase,
            batch=batch_idx,
            batches_total=batches_total,
            workers=workers,
            samples=len(samples),
            started_at=started,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
        )
        return samples

    if workers == 1 or batches_total <= 1:
        parts = [compute(item) for item in indexed]
    else:
        pool = ChunkComputePool(
            workers,
            thread_name_prefix="climate-compute",
            log_diagnostics=True,
        )
        try:
            parts = await pool.map_sync(indexed, compute)
        finally:
            pool.shutdown()
    stitched: list[ClimateSampleWire] = []
    for part in parts:
        stitched.extend(part)
    return stitched


class ClimatePackBakeOrchestrator:
    def __init__(
        self,
        *,
        read_context: PackReadContext | None = None,
        bake_defaults: PackBakeDefaults | None = None,
    ) -> None:
        self._read_ctx = read_context
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()

    async def bake_coarse(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        *,
        locations: list[NamedLocation] | None = None,
    ) -> tuple[PersistResult, int]:
        """Write climate_coarse.zst. Returns (blob PersistResult, sample count)."""
        climate_t0 = time.perf_counter()
        uid_map = (
            {loc.location_uid: loc for loc in locations}
            if locations is not None
            else None
        )
        bbox = surface_ctx.coarse_hm.bbox
        workers = resolve_climate_workers(mat_ctx, world)
        width = bbox.x_max - bbox.x_min + 1
        samples = await _map_climate_row_batches(
            workers,
            coarse_gy_rows(bbox),
            lambda gys: sample_climate_coarse_gy_rows(
                world,
                surface_ctx.pole_field,
                bbox,
                gys,
                local_field=surface_ctx.local_field,
                coarse_surface_z=surface_ctx.coarse_surface_z,
                uid_map=uid_map,
            ),
            world_uid=world.world_uid,
            phase="coarse",
            samples_per_row=width,
        )
        coarse = build_climate_coarse_wire(
            world,
            surface_ctx.pole_field,
            bbox,
            local_field=surface_ctx.local_field,
            coarse_surface_z=surface_ctx.coarse_surface_z,
            uid_map=uid_map,
            samples=samples,
        )
        climate_hash = writer.write_climate_coarse(coarse)
        log_pack_climate_coarse_done(
            world.world_uid,
            samples=len(coarse.samples),
            content_hash=climate_hash,
            started_at=climate_t0,
        )
        if self._read_ctx is not None:
            self._read_ctx.invalidate_climate(world)
        return PersistResult.from_counts(1, 1), len(coarse.samples)

    async def bake_fine_tile(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        tile_gx: int,
        tile_gy: int,
        *,
        parent_light: ParentLightTile | None = None,
        l2_surface_z: Mapping[tuple[int, int], int] | None = None,
        locations: list[NamedLocation] | None = None,
    ) -> tuple[PersistResult, int]:
        """Write denser per-tile climate. Returns (blob PersistResult, sample count)."""
        side = resolve_world_map_cells_per_tile(
            map_cell_fine_span(world),
            world.world_map_cells_per_tile,
        )
        uid_map = (
            {loc.location_uid: loc for loc in locations}
            if locations is not None
            else None
        )
        tile_m = map_cell_fine_span(world)
        scale = LightGridScale.from_tile(tile_m, side)
        step = scale.light_m
        origin_x = int(grid_tile_origin_x(tile_gx, tile_m))
        origin_y = int(grid_tile_origin_y(tile_gy, tile_m))
        l2_lookup = (
            bucket_l2_z_by_light_cell(
                l2_surface_z,
                origin_x=origin_x,
                origin_y=origin_y,
                light_span=step,
            )
            if l2_surface_z is not None
            else None
        )
        workers = resolve_climate_workers(mat_ctx, world)
        samples = await _map_climate_row_batches(
            workers,
            list(range(side)),
            lambda tys: sample_climate_tile_ty_rows(
                world,
                surface_ctx.pole_field,
                origin_x=origin_x,
                origin_y=origin_y,
                step=step,
                side=side,
                ty_rows=tys,
                local_field=surface_ctx.local_field,
                coarse_surface_z=surface_ctx.coarse_surface_z,
                meter_z_overrides=surface_ctx.meter_z_overrides,
                parent_light=parent_light,
                l2_surface_z=l2_lookup,
                uid_map=uid_map,
            ),
            world_uid=world.world_uid,
            phase="fine",
            samples_per_row=side,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
        )
        tile_field = build_climate_tile_wire(
            world,
            surface_ctx.pole_field,
            tile_gx,
            tile_gy,
            local_field=surface_ctx.local_field,
            cells_per_side=side,
            coarse_surface_z=surface_ctx.coarse_surface_z,
            meter_z_overrides=surface_ctx.meter_z_overrides,
            parent_light=parent_light,
            uid_map=uid_map,
            samples=samples,
        )
        writer.write_climate_tile(tile_gx, tile_gy, tile_field)
        log_pack_climate_tile_done(
            world.world_uid,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            samples=len(tile_field.samples),
        )
        if self._read_ctx is not None:
            self._read_ctx.invalidate_climate_tile(world, tile_gx, tile_gy)
        return PersistResult.from_counts(1, 1), len(tile_field.samples)

    async def bake_fine_tile_with_parent(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        tile_gx: int,
        tile_gy: int,
        *,
        l2_surface_z: Mapping[tuple[int, int], int] | None = None,
        locations: list[NamedLocation] | None = None,
        require_parent: bool = True,
    ) -> bool:
        """Load parent light and bake fine. Skip (False) when parent missing and required."""
        tile_m = map_cell_fine_span(world)
        parent = load_parent_light(
            world.world_uid,
            tile_gx,
            tile_gy,
            reader=WorldPackReader(writer.paths),
            cache=writer.parent_light_cache,
            tile_m=tile_m,
        )
        if parent is None and require_parent:
            logger.warning(
                "climate_fine_skip_no_parent_light | world=%s gx=%d gy=%d",
                world.world_uid,
                tile_gx,
                tile_gy,
            )
            return False
        await self.bake_fine_tile(
            world, surface_ctx, writer, mat_ctx, tile_gx, tile_gy,
            parent_light=parent,
            l2_surface_z=l2_surface_z,
            locations=locations,
        )
        return True

    async def bake_fine_for_l0_policy(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        tiles: list[tuple[int, int]],
        locations: list[NamedLocation],
        *,
        scope: PackTilePlanScope,
        anchor_x: int | None,
        anchor_y: int | None,
    ) -> int:
        """Bake fine tiles for light/full policy. Returns count baked."""
        policy: LightFineTilePolicy = (
            self._defaults.full_fine_tile_policy
            if scope == "full"
            else self._defaults.light_fine_tile_policy
        )
        fine_tiles = resolve_fine_tiles_for_policy(
            policy, tiles, world, locations, anchor_x=anchor_x, anchor_y=anchor_y,
        )
        baked = 0
        for gx, gy in fine_tiles:
            if await self.bake_fine_tile_with_parent(
                world, surface_ctx, writer, mat_ctx, gx, gy,
                locations=locations,
                require_parent=True,
            ):
                baked += 1
        return baked
