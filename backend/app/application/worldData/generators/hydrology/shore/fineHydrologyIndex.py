"""Declared hydrology carve at world fine-grid resolution."""

from __future__ import annotations

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.coordinates.worldTile import (
    expand_coarse_hydro_to_tile,
    fine_bbox_for_tile,
)
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import (
    segments_from_declared,
)
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    load_declared_hydrology,
)
from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import (
    resolve_declared_river_intents,
)
from app.application.worldData.generators.hydrology.load.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.hydrology.rivers.riverBedCarver import (
    _channel_depth_step,
    river_bed_spec,
    river_bed_roles,
)
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.application.worldData.generators.coordinates.convert import map_cell_fine_span
from app.dataModel.topology.fineTopology import fine_topology
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.application.worldData.generators.terrain.worldMapSettings import world_z_min
from app.application.worldData.generators.terrain.reliefObjects.riverBed import apply_river_bed_z
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def apply_declared_fine_river_carves(
    world: World,
    locations: list[NamedLocation],
    base_surface_z: dict[tuple[int, int], int],
    *, base_space: CoordinateSpace = CoordinateSpace.WORLD_FINE_GRID,
    coarse_hydro: dict[tuple[int, int], MapCellHydrology] | None = None,
) -> tuple[dict[tuple[int, int], MapCellHydrology], dict[tuple[int, int], int]]:
    """Rasterize fine rivers; sample coarse input explicitly, never invent floor z."""
    if base_space not in (CoordinateSpace.WORLD_FINE_GRID, CoordinateSpace.WORLD_SURFACE_GRID):
        raise ValueError(f"unsupported river base space: {base_space}")
    loaded = load_declared_hydrology(world, locations)
    type_classify = resolve_river_type_classify(world)
    merged_hydro: dict[tuple[int, int], MapCellHydrology] = {}
    surface_z: dict[tuple[int, int], int] = dict(base_surface_z)

    if surface_z:
        xs = [x for x, _ in surface_z]
        ys = [y for _, y in surface_z]
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(min(xs), max(xs), min(ys), max(ys)),
            surface_z=surface_z,
        )
    else:
        hm = SurfaceHeightmap(
            world_uid=world.world_uid,
            bbox=GridBBox(0, 0, 0, 0),
            surface_z={},
        )

    coarse_topology = resolve_hydrology_topology(world)
    topology = fine_topology(coarse_topology, map_cell_fine_span(world)) if coarse_topology else None
    segments = segments_from_declared(loaded.river_edges, topology=topology)
    segments.extend(resolve_declared_river_intents(
        world, hm, loaded.river_intents, locations, {}, type_classify,
        space=CoordinateSpace.WORLD_FINE_GRID, topology=topology,
    ))
    occupied = {}
    if base_space is CoordinateSpace.WORLD_SURFACE_GRID:
        from app.application.worldData.generators.coordinates.convert import fine_to_grid_xy
        from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import classify_autoresolve_polyline
        from dataclasses import replace

        span = map_cell_fine_span(world)
        samples = {cell: fine_to_grid_xy(*cell, span)
                   for segment in segments for cell in segment.polyline_cells}
        surface_z = {cell: base_surface_z[grid] for cell, grid in samples.items() if grid in base_surface_z}
        hm = replace(hm, surface_z=surface_z)
        occupied = {cell: coarse_hydro[grid] for cell, grid in samples.items()
                    if coarse_hydro is not None and grid in coarse_hydro}
        segments = [segment if segment.declared else replace(segment, connection_type=
            classify_autoresolve_polyline(segment.polyline_cells, hm, type_classify,
                                         edge_uid=segment.edge_uid).connection_type)
                    for segment in segments]
    specs = []
    for segment in segments:
        spec = river_bed_spec(hm, segment,
            depth_step=_channel_depth_step(segment.connection_type, type_classify),
            occupied=occupied, z_min=world_z_min(world))
        specs.append(spec)
        merged_hydro.update(river_bed_roles(segment, spec))
    apply_river_bed_z(hm, specs)

    return merged_hydro, surface_z


def merge_fine_hydro_for_tile(
    tile_gx: int,
    tile_gy: int,
    map_cell: int,
    coarse_hydro: dict[tuple[int, int], MapCellHydrology],
    sparse_fine_hydro: dict[tuple[int, int], MapCellHydrology],
) -> dict[tuple[int, int], MapCellHydrology]:
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    merged.update(expand_coarse_hydro_to_tile(coarse_hydro, tile_gx, tile_gy, map_cell))

    fine_bbox = fine_bbox_for_tile(tile_gx, tile_gy, map_cell)
    for (xm, ym), entry in sparse_fine_hydro.items():
        if (
            fine_bbox.x_min <= xm <= fine_bbox.x_max
            and fine_bbox.y_min <= ym <= fine_bbox.y_max
        ):
            merged[(xm, ym)] = entry

    return merged
