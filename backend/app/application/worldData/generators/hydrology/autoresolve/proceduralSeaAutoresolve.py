"""Procedural coastal sea / open ocean autoresolve — D HY-5a."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import (
    _shelf_depth,
    compute_land_centroid,
    declare_coastline_bbox_padded,
    flood_from_bbox_ocean_edge,
    flood_water_side_unbounded,
    land_shore_from_water_dist,
)
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.load.resolveHydrologyBands import resolve_hydrology_bands
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.hydrology.types import HydrologyBands, HydrologyMasterInput
from app.application.worldData.generators.hydrology.waterBodyIdentity import (
    AutoWaterBodyRole,
    auto_water_body_uid,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.topologyGeometry import unrolled_images


def _outside_bbox(cell: tuple[int, int], bbox: GridBBox, topology: WorldTopology) -> bool:
    anchor = (bbox.x_min + bbox.x_max) / 2, (bbox.y_min + bbox.y_max) / 2
    return not any(bbox.x_min <= image.coord[0] <= bbox.x_max
                   and bbox.y_min <= image.coord[1] <= bbox.y_max
                   for image in unrolled_images(topology, cell, anchor=anchor))


def _carve_water_candidates(
    heightmap: SurfaceHeightmap,
    candidates: dict[tuple[int, int], int],
    bands: HydrologyBands,
    level: int,
    *,
    water_body_uid: str,
    autoresolve_coastal: bool,
    autoresolve_open_ocean: bool,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    if not candidates:
        return {}, None

    shelf_depth = _shelf_depth(bands, candidates)
    by_cell: dict[tuple[int, int], MapCellHydrology] = {}
    xs: list[int] = []
    ys: list[int] = []

    for cell, distance in candidates.items():
        if distance <= shelf_depth:
            if not autoresolve_coastal:
                continue
            deepening = distance
            heightmap.surface_z[cell] = max(level, level + (shelf_depth - deepening + 1))
            by_cell[cell] = MapCellHydrology.shore(
                HydrologyShoreKind.SEA,
                deepening_index=deepening,
                water_body_uid=water_body_uid,
            )
        else:
            heightmap.surface_z[cell] = level
            if autoresolve_open_ocean:
                by_cell[cell] = MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN,
                                               water_body_uid=water_body_uid)
            elif autoresolve_coastal:
                by_cell[cell] = MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA,
                                               water_body_uid=water_body_uid)

        xs.append(cell[0])
        ys.append(cell[1])

    dirty = None
    if xs and ys:
        dirty = GridBBox(min(xs), max(xs), min(ys), max(ys))
    return by_cell, dirty


def _autoresolve_beyond_declare_bbox(
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology],
    bands: HydrologyBands,
    level: int,
    *,
    topology: WorldTopology,
    autoresolve_coastal: bool,
    autoresolve_open_ocean: bool,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    segments = master.declared_coastline_segments
    declare_bbox = declare_coastline_bbox_padded(segments)
    if declare_bbox is None:
        return {}, None

    coastline_cells = rasterize_segments(segments, topology=topology)
    water_dist = flood_water_side_unbounded(heightmap, coastline_cells, segments, topology=topology)
    candidates = {
        cell: distance
        for cell, distance in water_dist.items()
        if cell not in occupied and _outside_bbox(cell, declare_bbox, topology)
    }
    if not candidates:
        return {}, None
    uid = auto_water_body_uid(AutoWaterBodyRole.SEA, min(candidates))
    return _carve_water_candidates(
        heightmap,
        candidates,
        bands,
        level,
        water_body_uid=uid,
        autoresolve_coastal=autoresolve_coastal,
        autoresolve_open_ocean=autoresolve_open_ocean,
    )


def _autoresolve_from_map_boundary(
    heightmap: SurfaceHeightmap,
    occupied: dict[tuple[int, int], MapCellHydrology],
    bands: HydrologyBands,
    level: int,
    *,
    topology: WorldTopology,
    autoresolve_coastal: bool,
    autoresolve_open_ocean: bool,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    water_dist = flood_from_bbox_ocean_edge(heightmap, topology=topology)
    if not water_dist:
        return {}, None

    uid = auto_water_body_uid(AutoWaterBodyRole.SEA, min(water_dist))
    land_centroid = compute_land_centroid(heightmap, topology=topology)
    land_shore = land_shore_from_water_dist(heightmap, water_dist, land_centroid, topology=topology)
    by_cell: dict[tuple[int, int], MapCellHydrology] = {}

    for cell in land_shore:
        if cell in occupied:
            continue
        by_cell[cell] = MapCellHydrology.shore(
            HydrologyShoreKind.SEA,
            deepening_index=0,
            water_body_uid=uid,
        )

    candidates = {
        cell: distance
        for cell, distance in water_dist.items()
        if cell not in occupied
    }
    carved, _ = _carve_water_candidates(
        heightmap,
        candidates,
        bands,
        level,
        water_body_uid=uid,
        autoresolve_coastal=autoresolve_coastal,
        autoresolve_open_ocean=autoresolve_open_ocean,
    )
    by_cell.update(carved)

    dirty = None
    if by_cell:
        cells = list(by_cell.keys())
        dirty = GridBBox(
            min(c[0] for c in cells),
            max(c[0] for c in cells),
            min(c[1] for c in cells),
            max(c[1] for c in cells),
        )
    return by_cell, dirty


def autoresolve_sea_basins(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology],
    *,
    autoresolve_coastal: bool,
    autoresolve_open_ocean: bool,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    """
    Declare + autoresolve (C7b) when coastline edges exist; else bbox-edge flood (procedural v1).
    """
    if not autoresolve_coastal and not autoresolve_open_ocean:
        return {}, None

    bands = resolve_hydrology_bands("seas", world, world_uid=master.world_uid)
    level = resolve_z_sea(world)
    topology = resolve_hydrology_topology(world, heightmap)

    if master.declared_coastline_segments:
        return _autoresolve_beyond_declare_bbox(
            heightmap,
            master,
            occupied,
            bands,
            level,
            topology=topology,
            autoresolve_coastal=autoresolve_coastal,
            autoresolve_open_ocean=autoresolve_open_ocean,
        )

    return _autoresolve_from_map_boundary(
        heightmap,
        occupied,
        bands,
        level,
        topology=topology,
        autoresolve_coastal=autoresolve_coastal,
        autoresolve_open_ocean=autoresolve_open_ocean,
    )
