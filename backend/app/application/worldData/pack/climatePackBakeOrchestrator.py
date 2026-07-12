"""Climate pack bake phases — coarse light + fine per-tile (CL-PACK-1)."""

from __future__ import annotations

import time

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.climateCoarseBake import (
    build_climate_coarse_wire,
    build_climate_tile_wire,
)
from app.application.worldData.pack.packBakeLog import (
    log_pack_climate_coarse_done,
    log_pack_climate_tile_done,
)
from app.application.worldData.pack.packReadContext import PackReadContext
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.application.worldData.persistResult import PersistResult
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.db.models.world import World


class ClimatePackBakeOrchestrator:
    def __init__(self, *, read_context: PackReadContext | None = None) -> None:
        self._read_ctx = read_context

    def bake_coarse(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
    ) -> tuple[PersistResult, int]:
        """Write climate_coarse.zst. Returns (blob PersistResult, sample count)."""
        climate_t0 = time.perf_counter()
        coarse = build_climate_coarse_wire(
            world,
            surface_ctx.pole_field,
            surface_ctx.coarse_hm.bbox,
            coarse_surface_z=surface_ctx.coarse_surface_z,
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

    def bake_fine_tile(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
        tile_gx: int,
        tile_gy: int,
    ) -> tuple[PersistResult, int]:
        """Write denser per-tile climate. Returns (blob PersistResult, sample count)."""
        side = resolve_world_map_cells_per_tile(
            cell_size_m(world),
            world.world_map_cells_per_tile,
        )
        tile_field = build_climate_tile_wire(
            world,
            surface_ctx.pole_field,
            tile_gx,
            tile_gy,
            cells_per_side=side,
            coarse_surface_z=surface_ctx.coarse_surface_z,
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
