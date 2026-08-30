"""Serial prep before FineChunkRunner pool — parent, surface, halo, catalog."""

from __future__ import annotations

from app.application.worldData.generators.coordinates import cell_size_m
from app.application.worldData.generators.coordinates.worldTile import meter_bbox_for_tile
from app.application.worldData.generators.terrain.passes.bbox import world_bounds_from_world
from app.application.worldData.generators.terrain.passes.surfaceTerrainContext import (
    SurfaceTerrainContext,
)
from app.application.worldData.generators.terrain.types import ColumnRect
from app.application.worldData.generators.terrain.worldMapSettings import (
    force_serial_terrain_generate,
    terrain_chunk_columns,
)
from app.application.worldData.materializationContext import MaterializationContext
from app.application.worldData.pack.bake.packBakeLog import log_pack_fine_terrain_workers
from app.application.worldData.pack.io.worldPackReader import WorldPackReader
from app.application.worldData.pack.io.worldPackWriter import WorldPackWriter
from app.application.worldData.pack.read.locationTerritoryVolumes import (
    territory_volumes_by_location,
)
from app.application.worldData.pack.read.parentLightLoad import require_parent_light
from app.application.worldData.pack.refine.detailedGradeCatalog import catalog_for_surface
from app.application.worldData.pack.refine.detailedGradeHalo import grade_halo_cells
from app.application.worldData.pack.refine.entryRingGeom import wilderness_chunk_origin
from app.application.worldData.pack.refine.fineTileContext import FineTileContext
from app.application.worldData.pack.refine.gridNeighborHalo import overlay_grid_neighbor_halos
from app.application.worldData.parallelPolicy import resolve_terrain_workers
from app.application.worldData.terrainBatchOrchestrator import (
    TerrainBatchOrchestrator,
    refresh_tile_gaps,
)
from app.dataModel.terrain.relief.reliefTemplate import ReliefTemplate
from app.dataModel.worldPack.fineTerrainChunkWire import FineTerrainChunkWire
from app.dataModel.worldPack.gradePipelineStages import GradePipelineStages
from app.dataModel.worldPack.territoryVolume import TerritoryVolume
from app.dataModel.worldPack.worldPackManifest import ChunkRefineRole
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def prepare_fine_tile(
    terrain: TerrainBatchOrchestrator,
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
    relief_templates_by_uid: dict[str, ReliefTemplate] | None = None,
    stages: GradePipelineStages | None = None,
) -> FineTileContext:
    """Prep before the pool: parent light, upsample + hills + hydro, halo, catalog."""
    phase_name = phase or refine_role
    stages = stages or GradePipelineStages.off()
    run_mill = stages.mill
    run_paint = stages.paint
    chunk_size = terrain_chunk_columns(world)
    cell_m = cell_size_m(world)
    meter_bbox = meter_bbox_for_tile(tile_gx, tile_gy, cell_m)
    location_pairs = territory_volumes_by_location(world, locations)
    reader = WorldPackReader(writer.paths)
    parent = require_parent_light(
        world.world_uid,
        tile_gx,
        tile_gy,
        reader=reader,
        cache=writer.parent_light_cache,
        tile_m=cell_m,
    )
    surface_state = terrain.build_tile_surface_state(
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
    templates = (relief_templates_by_uid or {}) if run_mill else {}
    existing_uids = (
        existing_grade_uids_from_pack(
            writer, reader, tile_gx, tile_gy, meter_bbox, chunk_size,
        )
        if run_mill
        else {}
    )
    catalog = (
        catalog_for_surface(
            world, meter_bbox, tile_gx=tile_gx, tile_gy=tile_gy, chunk_size=chunk_size,
        )
        if run_paint
        else None
    )
    grade_halo = grade_halo_cells(templates) if templates else 0
    bounds = world_bounds_from_world(world, locations)
    if templates and bounds is not None and grade_halo > 0:
        surface_state = overlay_grid_neighbor_halos(
            surface_state,
            world_uid=world.world_uid,
            tile_gx=tile_gx,
            tile_gy=tile_gy,
            this_bbox=meter_bbox,
            halo=grade_halo,
            bounds=bounds,
            reader=reader,
            cache=writer.parent_light_cache,
            tile_m=cell_m,
            writer=writer,
            chunk_size=chunk_size,
        )
        surface_state = refresh_tile_gaps(world, surface_state)
    return FineTileContext(
        world=world,
        locations=locations,
        surface_ctx=surface_ctx,
        tile_gx=tile_gx,
        tile_gy=tile_gy,
        meter_bbox=meter_bbox,
        chunk_size=chunk_size,
        surface_state=surface_state,
        templates=templates,
        grade_halo=grade_halo,
        existing_uids=existing_uids,
        catalog=catalog,
        workers=workers,
        refine_role=refine_role,
        phase_name=phase_name,
        world_uid=world.world_uid,
        chunks_total=chunks_total,
        location_pairs=location_pairs,
        volumes=volumes,
        stages=stages,
    )


def existing_grade_uids_from_pack(
    writer: WorldPackWriter,
    reader: WorldPackReader,
    tile_gx: int,
    tile_gy: int,
    meter_bbox: ColumnRect,
    chunk_size: int,
) -> dict[tuple[int, int], str]:
    """Late-chunk inherit: uids already on wilderness columns (R36v)."""
    tile = writer.manifest.tile_entry(tile_gx, tile_gy)
    if tile is None or not tile.chunks:
        return {}
    out: dict[tuple[int, int], str] = {}
    for ref in tile.chunks:
        try:
            chunk: FineTerrainChunkWire = reader.read_wilderness_chunk(
                tile_gx, tile_gy, ref.cx, ref.cy,
            )
        except (OSError, ValueError, FileNotFoundError):
            continue
        origin_x, origin_y = wilderness_chunk_origin(
            meter_bbox, int(ref.cx), int(ref.cy), chunk_size,
        )
        for col in chunk.columns:
            uid = col.system_grade_uid
            if not uid:
                continue
            out[(origin_x + int(col.lx), origin_y + int(col.ly))] = uid
    return out
