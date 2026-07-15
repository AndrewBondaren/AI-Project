"""detailed_bake — L2 location_terrain for one location (WP-27).

Reuses ``FineChunkRunner``; does not clone L0 bake or entry session.
"""

from __future__ import annotations

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import (
    iter_meter_chunks,
    macro_tile_of,
    meter_bbox_for_tile,
)
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    terrain_chunk_columns,
)
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volume_for_location,
)
from app.application.worldData.pack.read.parentLightLoad import require_parent_light
from app.application.worldData.pack.refine.fineChunkRunner import FineChunkRunner
from app.application.worldData.persistResult import PersistResult
from app.application.worldData.terrainBatchOrchestrator import TerrainBatchOrchestrator
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

DETAILED_REFINE_ROLE: ChunkRefineRole = "location"


def _rect_overlaps_volume(rect: ColumnRect, volume: TerritoryVolume) -> bool:
    return not (
        rect.x_max < volume.x0
        or rect.x_min > volume.x1
        or rect.y_max < volume.y0
        or rect.y_min > volume.y1
    )


def tiles_covering_volume(world: World, volume: TerritoryVolume) -> list[tuple[int, int]]:
    cell_m = cell_size_m(world)
    corners = (
        (volume.x0, volume.y0),
        (volume.x0, volume.y1),
        (volume.x1, volume.y0),
        (volume.x1, volume.y1),
    )
    tiles = {macro_tile_of(x, y, cell_m) for x, y in corners}
    gxs = [g for g, _ in tiles]
    gys = [g for _, g in tiles]
    out: list[tuple[int, int]] = []
    for gy in range(min(gys), max(gys) + 1):
        for gx in range(min(gxs), max(gxs) + 1):
            out.append((gx, gy))
    return out


def rects_for_volume_on_tile(
    world: World,
    volume: TerritoryVolume,
    tile_gx: int,
    tile_gy: int,
) -> list[ColumnRect]:
    cell_m = cell_size_m(world)
    meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
    chunk_size = terrain_chunk_columns(world)
    return [
        rect
        for rect in iter_meter_chunks(meter_bbox, chunk_size)
        if _rect_overlaps_volume(rect, volume)
    ]


class PackDetailedBakeOrchestrator:
    """Bake L2 ``location_terrain`` for one ``location_uid`` from parent light."""

    def __init__(
        self,
        terrain: TerrainBatchOrchestrator,
        *,
        runner: FineChunkRunner | None = None,
    ) -> None:
        self._runner = runner or FineChunkRunner(terrain)

    async def bake_location(
        self,
        world: World,
        locations: list[NamedLocation],
        writer: WorldPackWriter,
        mat_ctx: MaterializationContext,
        surface_ctx: SurfaceTerrainContext,
        location_uid: str,
    ) -> PersistResult:
        location = next((loc for loc in locations if loc.location_uid == location_uid), None)
        if location is None:
            raise ValueError(f"location_uid not found: {location_uid}")
        volume = territory_volume_for_location(world, location)
        if volume is None:
            raise ValueError(
                f"location {location_uid} has no territory volume (missing map_x/map_y)",
            )

        tiles = tiles_covering_volume(world, volume)
        if not tiles:
            raise ValueError(f"location {location_uid}: no macro-tiles for territory")

        tile_m = cell_size_m(world)
        reader = WorldPackReader(writer.paths)
        cache = writer.parent_light_cache
        for gx, gy in tiles:
            require_parent_light(
                world.world_uid, gx, gy,
                reader=reader, cache=cache, tile_m=tile_m,
            )

        aggregate = PersistResult.from_counts(0, 0)
        for gx, gy in tiles:
            rects = rects_for_volume_on_tile(world, volume, gx, gy)
            if not rects:
                continue
            result, _written, _n = await self._runner.refine_rects(
                world, locations, writer, mat_ctx, surface_ctx,
                gx, gy, rects, [volume],
                refine_role=DETAILED_REFINE_ROLE,
                phase="detailed",
            )
            aggregate = PersistResult.from_counts(
                aggregate.total + result.total,
                aggregate.succeeded + result.succeeded,
                failed=aggregate.failed + result.failed,
            )

        writer.recalc_manifest_counters()
        writer.save_manifest()
        return aggregate
