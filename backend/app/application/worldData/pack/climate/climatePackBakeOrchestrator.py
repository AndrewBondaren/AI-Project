"""Climate pack bake phases — coarse light + fine per-tile (CL-PACK-1)."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.climate.climateCoarseBake import (
    build_climate_coarse_wire,
    build_climate_tile_wire,
)
from app.application.worldData.pack.climate.lightFineTileResolve import (
    resolve_fine_tiles_for_policy,
)
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_climate_coarse_done,
    log_pack_climate_tile_done,
)
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.read.packReadContext import PackReadContext
from app.application.worldData.pack.read.parentLightLoad import load_parent_light
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.persistResult import PersistResult
from app.dataModel.worldPack.lightFineTilePolicy import LightFineTilePolicy
from app.dataModel.worldPack.parentLightTile import ParentLightTile
from app.dataModel.worldPack.packTilePlan import PackTilePlanScope
from app.dataModel.worldPack.packBakeDefaults import PackBakeDefaults
from app.dataModel.worldPack.worldMapCellsPerTile import resolve_world_map_cells_per_tile
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


class ClimatePackBakeOrchestrator:
    def __init__(
        self,
        *,
        read_context: PackReadContext | None = None,
        bake_defaults: PackBakeDefaults | None = None,
    ) -> None:
        self._read_ctx = read_context
        self._defaults = bake_defaults or PackBakeDefaults.canonical_defaults()

    def bake_coarse(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
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
        coarse = build_climate_coarse_wire(
            world,
            surface_ctx.pole_field,
            surface_ctx.coarse_hm.bbox,
            local_field=surface_ctx.local_field,
            coarse_surface_z=surface_ctx.coarse_surface_z,
            uid_map=uid_map,
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
        *,
        parent_light: ParentLightTile | None = None,
        l2_surface_z: Mapping[tuple[int, int], int] | None = None,
        locations: list[NamedLocation] | None = None,
    ) -> tuple[PersistResult, int]:
        """Write denser per-tile climate. Returns (blob PersistResult, sample count)."""
        side = resolve_world_map_cells_per_tile(
            cell_size_m(world),
            world.world_map_cells_per_tile,
        )
        uid_map = (
            {loc.location_uid: loc for loc in locations}
            if locations is not None
            else None
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
            l2_surface_z=l2_surface_z,
            uid_map=uid_map,
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

    def bake_fine_tile_with_parent(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
        tile_gx: int,
        tile_gy: int,
        *,
        l2_surface_z: Mapping[tuple[int, int], int] | None = None,
        locations: list[NamedLocation] | None = None,
        require_parent: bool = True,
    ) -> bool:
        """Load parent light and bake fine. Skip (False) when parent missing and required."""
        tile_m = cell_size_m(world)
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
        self.bake_fine_tile(
            world, surface_ctx, writer, tile_gx, tile_gy,
            parent_light=parent,
            l2_surface_z=l2_surface_z,
            locations=locations,
        )
        return True

    def bake_fine_for_l0_policy(
        self,
        world: World,
        surface_ctx: SurfaceTerrainContext,
        writer: WorldPackWriter,
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
            if self.bake_fine_tile_with_parent(
                world, surface_ctx, writer, gx, gy,
                locations=locations,
                require_parent=True,
            ):
                baked += 1
        return baked
