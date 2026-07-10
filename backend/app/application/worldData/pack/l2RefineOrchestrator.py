"""L2 chunk refine to pack — scene-volume blocking WP-13."""

from __future__ import annotations

import math

from app.application.worldData.persistResult import PersistResult
from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import iter_meter_chunks, meter_bbox_for_tile
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import terrain_chunk_columns
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.chunkRefineQueue import ChunkRefineQueue
from app.application.worldData.pack.locationTerritoryVolumes import territory_volumes_by_location
from app.application.worldData.pack.mapCellToL2Wire import cells_to_l2_chunk
from app.application.worldData.pack.packMapHelpers import tile_index, world_tile_size_m
from app.application.worldData.pack.pathHeading import (
    PathHeading,
    filter_corridor_rects,
    macro_tiles_ahead,
)
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.worldPack.pathHeadingPolicy import PathHeadingPolicy
from app.dataModel.worldPack.territoryVolume import TerritoryVolume, inside_location_volume
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _chunk_center(rect: ColumnRect) -> tuple[float, float]:
    return (rect.x_min + rect.x_max) / 2.0, (rect.y_min + rect.y_max) / 2.0


def _distance_sq(ax: float, ay: float, bx: float, by: float) -> float:
    return (ax - bx) ** 2 + (ay - by) ** 2


def _tile_local_chunk_indices(
    rect: ColumnRect,
    meter_bbox: ColumnRect,
    chunk_size: int,
) -> tuple[int, int]:
    return (
        (rect.x_min - meter_bbox.x_min) // chunk_size,
        (rect.y_min - meter_bbox.y_min) // chunk_size,
    )


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


class L2RefineOrchestrator:
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
        surface_ctx,
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
            if _distance_sq(*_chunk_center(rect), anchor_x, anchor_y) <= (xy_radius + chunk_size) ** 2
        ]
        return await self._refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, scene_rects, loc_volumes,
            refine_role="scene",
        )

    async def refine_rect(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx,
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
    ) -> int:
        cell_m = cell_size_m(world)
        chunk_size = terrain_chunk_columns(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        skip = skip_scene_rects or set()
        count = 0
        for rect in iter_meter_chunks(meter_bbox, chunk_size):
            cx, cy = _tile_local_chunk_indices(rect, meter_bbox, chunk_size)
            if (cx, cy) in skip:
                continue
            if queue.enqueue_chunk(
                tile_gx, tile_gy, cx, cy,
                anchor_x=float(anchor_x),
                anchor_y=float(anchor_y),
                chunk_columns=chunk_size,
                tile_size_m=cell_m,
            ):
                count += 1
        return count

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
        """Enqueue background chunks on macro-tiles ahead along heading (WP-17)."""
        tile_size = world_tile_size_m(world)
        count = 0
        for ngx, ngy in macro_tiles_ahead(tile_gx, tile_gy, heading, depth_tiles):
            count += await self.schedule_tile_background(
                world, queue, anchor_x, anchor_y, ngx, ngy,
            )
        return count

    async def refine_queued_chunk(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx,
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
        surface_ctx,
        tile_gx: int,
        tile_gy: int,
        rects: list[ColumnRect],
        volumes: list[TerritoryVolume],
        *,
        refine_role: str = "scene",
    ) -> tuple[PersistResult, int, int]:
        chunk_size = terrain_chunk_columns(world)
        cell_m = cell_size_m(world)
        meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
        location_pairs = territory_volumes_by_location(world, locations)
        surface_state = self._terrain.build_tile_surface_state(
            world, locations, surface_ctx, tile_gx, tile_gy,
        )
        location_cells: dict[str, list[MapCell]] = {}
        total_cells = 0
        written = 0
        for rect in rects:
            cells = await self._terrain.generate_chunk_cells(
                world, locations, surface_ctx, tile_gx, tile_gy, rect,
                surface_state=surface_state,
            )
            wilderness: list[MapCell] = []
            for cell in cells:
                hit = _location_for_cell(cell.x, cell.y, cell.z, location_pairs)
                if hit is not None:
                    location_uid, _ = hit
                    location_cells.setdefault(location_uid, []).append(cell)
                elif not inside_location_volume(cell.x, cell.y, cell.z, volumes):
                    wilderness.append(cell)
            cx, cy = _tile_local_chunk_indices(rect, meter_bbox, chunk_size)
            if wilderness:
                chunk = cells_to_l2_chunk(
                    cx, cy, chunk_size, rect.x_min, rect.y_min, wilderness,
                )
                writer.write_l2_wilderness_chunk(
                    tile_gx, tile_gy, chunk,
                    refine_role=refine_role,  # type: ignore[arg-type]
                )
                total_cells += len(wilderness)
                written += 1
        for location_uid, loc_cells in location_cells.items():
            volume = next((vol for uid, vol in location_pairs if uid == location_uid), None)
            if volume is None or not loc_cells:
                continue
            chunk = cells_to_l2_chunk(0, 0, chunk_size, volume.x0, volume.y0, loc_cells)
            writer.write_location_l2(location_uid, chunk, territory_volume=volume)
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
        surface_ctx,
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
        result, written, _ = await self._refine_rects(
            world, locations, writer, mat_ctx, surface_ctx,
            tile_gx, tile_gy, corridor, loc_volumes,
            refine_role="path",
        )
        return written

    @staticmethod
    def tile_for_anchor(world: World, anchor_x: int, anchor_y: int) -> tuple[int, int]:
        tile_size = world_tile_size_m(world)
        gx, _ = tile_index(anchor_x, tile_size)
        gy, _ = tile_index(anchor_y, tile_size)
        return gx, gy
