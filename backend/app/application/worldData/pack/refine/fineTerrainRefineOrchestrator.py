"""L2 fine-terrain refine facade — WP-13 scene / path / queued chunk.

Delegates generate+persist to ``FineChunkRunner``, enqueue to ``chunkSchedule``,
corridor select to ``pathCorridorSelect``. Public method names stable for
``EntryRefineOrchestrator`` / ``ChunkRefineWorker``.
"""

from __future__ import annotations

from app.application.worldData.persistResult import PersistResult
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import meter_bbox_for_tile
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.packBakeLog import (
    log_pack_fine_terrain_phase_done,
    log_pack_fine_terrain_phase_start,
)
from app.application.worldData.pack.refine.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.refine.chunkSchedule import (
    schedule_path_ahead_tiles as schedule_path_ahead_tiles_fn,
    schedule_tile_background as schedule_tile_background_fn,
)
from app.application.worldData.pack.refine.entryRingGeom import (
    chunk_within_ring,
    scene_chunk_indices as geom_scene_chunk_indices,
)
from app.application.worldData.pack.refine.fineChunkRunner import FineChunkRunner
from app.application.worldData.pack.refine.pathCorridorSelect import (
    select_path_corridor_rects,
)
from app.application.worldData.pack.refine.pathHeading import PathHeading
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volumes_by_location,
)
from app.application.worldData.pack.read.packMapHelpers import tile_for_anchor
from app.application.worldData.pack.refine.meterChunkGeom import rects_for_macro_tile
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class FineTerrainRefineOrchestrator:
    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        runner: FineChunkRunner | None = None,
    ) -> None:
        self._terrain = terrain
        self._runner = runner or FineChunkRunner(terrain)

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
        loc_volumes = location_volumes or [
            vol for _, vol in territory_volumes_by_location(world, locations)
        ]
        rects = rects_for_macro_tile(world, tile_gx, tile_gy)
        chunk_size = terrain_chunk_columns(world)
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
        result = await self._runner.refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, scene_rects, loc_volumes,
            refine_role="scene",
            phase="scene",
        )
        log_pack_fine_terrain_phase_done(
            world.world_uid,
            "scene",
            chunks_written=result.wilderness_chunks_written,
            cells_total=result.persist.succeeded,
            started_at=phase_t0,
        )
        return result.persist, result.wilderness_chunks_written, result.rect_count

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
        refine_role: ChunkRefineRole = "background",
    ) -> int:
        loc_volumes = location_volumes or [
            vol for _, vol in territory_volumes_by_location(world, locations)
        ]
        result = await self._runner.refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, [rect], loc_volumes,
            refine_role=refine_role,
            phase=refine_role,
        )
        return result.persist.succeeded

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
        return await schedule_tile_background_fn(
            world, queue, anchor_x, anchor_y, tile_gx, tile_gy,
            skip_scene_rects=skip_scene_rects,
            max_radius_m=max_radius_m,
        )

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
        return await schedule_path_ahead_tiles_fn(
            world, queue, anchor_x, anchor_y, tile_gx, tile_gy, heading,
            depth_tiles=depth_tiles,
        )

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
        depth_tiles: int | None = None,
    ) -> int:
        """Refine coarse corridor ahead of anchor — PLAYER_PATH layer (MERGE-5 / DEBT-7)."""
        if heading is None or not heading.is_defined:
            return 0
        corridor = select_path_corridor_rects(
            world, tile_gx, tile_gy, anchor_x, anchor_y, heading,
            depth_tiles=depth_tiles,
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
        result = await self._runner.refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, corridor, loc_volumes,
            refine_role="path",
            phase="path",
        )
        log_pack_fine_terrain_phase_done(
            world.world_uid,
            "path",
            chunks_written=result.wilderness_chunks_written,
            cells_total=result.persist.succeeded,
            started_at=phase_t0,
        )
        return result.wilderness_chunks_written

    @staticmethod
    def tile_for_anchor(world: World, anchor_x: int, anchor_y: int) -> tuple[int, int]:
        return tile_for_anchor(world, anchor_x, anchor_y)

    # Compat for tests that called private _refine_rects
    async def _refine_rects(self, *args, **kwargs):
        return await self._runner.refine_rects(*args, **kwargs)
