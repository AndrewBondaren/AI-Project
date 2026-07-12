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
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.hydrology.types import HydrologyBands, HydrologyMasterInput
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def _outside_bbox(cell: tuple[int, int], bbox: GridBBox) -> bool:
    gx, gy = cell
    return gx < bbox.x_min or gx > bbox.x_max or gy < bbox.y_min or gy > bbox.y_max


def _carve_water_candidates(
    heightmap: SurfaceHeightmap,
    candidates: dict[tuple[int, int], int],
    bands: HydrologyBands,
    level: int,
    *,
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
            by_cell[cell] = MapCellHydrology(
                role=HydrologyCellRole.SHORE,
                deepening_index=deepening,
            )
        else:
            heightmap.surface_z[cell] = level
            if autoresolve_open_ocean:
                by_cell[cell] = MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)
            elif autoresolve_coastal:
                by_cell[cell] = MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA)

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
    autoresolve_coastal: bool,
    autoresolve_open_ocean: bool,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    segments = master.declared_coastline_segments
    declare_bbox = declare_coastline_bbox_padded(segments)
    if declare_bbox is None:
        return {}, None

    coastline_cells = rasterize_segments(segments)
    water_dist = flood_water_side_unbounded(heightmap, coastline_cells, segments)
    candidates = {
        cell: distance
        for cell, distance in water_dist.items()
        if cell not in occupied and _outside_bbox(cell, declare_bbox)
    }
    return _carve_water_candidates(
        heightmap,
        candidates,
        bands,
        level,
        autoresolve_coastal=autoresolve_coastal,
        autoresolve_open_ocean=autoresolve_open_ocean,
    )


def _autoresolve_from_map_boundary(
    heightmap: SurfaceHeightmap,
    occupied: dict[tuple[int, int], MapCellHydrology],
    bands: HydrologyBands,
    level: int,
    *,
    autoresolve_coastal: bool,
    autoresolve_open_ocean: bool,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    water_dist = flood_from_bbox_ocean_edge(heightmap)
    if not water_dist:
        return {}, None

    land_centroid = compute_land_centroid(heightmap)
    land_shore = land_shore_from_water_dist(heightmap, water_dist, land_centroid)
    by_cell: dict[tuple[int, int], MapCellHydrology] = {}

    for cell in land_shore:
        if cell in occupied:
            continue
        by_cell[cell] = MapCellHydrology(
            role=HydrologyCellRole.SHORE,
            deepening_index=0,
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

    if master.declared_coastline_segments:
        return _autoresolve_beyond_declare_bbox(
            heightmap,
            master,
            occupied,
            bands,
            level,
            autoresolve_coastal=autoresolve_coastal,
            autoresolve_open_ocean=autoresolve_open_ocean,
        )

    return _autoresolve_from_map_boundary(
        heightmap,
        occupied,
        bands,
        level,
        autoresolve_coastal=autoresolve_coastal,
        autoresolve_open_ocean=autoresolve_open_ocean,
    )
