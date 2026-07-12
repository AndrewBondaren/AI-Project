"""Declared lake basin carve — D HY-3 scope LAKES."""

from __future__ import annotations

from collections import deque
from typing import Any

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import _neighbors4
from app.application.worldData.generators.hydrology.geom.polygonInterior import interior_cells
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.load.hydrologyAutoresolvePolicy import (
    lakes_autoresolve_policy,
)
from app.application.worldData.generators.hydrology.load.resolveHydrologyBands import (
    resolve_hydrology_bands,
)
from app.application.worldData.generators.hydrology.types import (
    HydrologyMasterInput,
    LakeSpec,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def _land_shore_outside(
    shoreline: set[tuple[int, int]],
    interior: set[tuple[int, int]],
    heightmap: SurfaceHeightmap,
) -> set[tuple[int, int]]:
    land: set[tuple[int, int]] = set()
    for cell in shoreline:
        for n in _neighbors4(*cell):
            if n in heightmap.surface_z and n not in interior and n not in shoreline:
                land.add(n)
    return land


def _lake_shelf_depth(bands, interior_dist: dict[tuple[int, int], int]) -> int:
    if not interior_dist:
        return bands.max
    max_d = max(interior_dist.values())
    if max_d <= 1:
        return 0
    return min(bands.max, max(max_d - 1, bands.min))


def _interior_seed(
    heightmap: SurfaceHeightmap,
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    shoreline: set[tuple[int, int]],
) -> tuple[int, int] | None:
    from app.application.worldData.generators.hydrology.geom.polygonInterior import (
        point_in_polygon,
        polygon_vertices,
    )

    verts = polygon_vertices(segments)
    if len(verts) < 3:
        return None
    cx = sum(v[0] for v in verts) / len(verts)
    cy = sum(v[1] for v in verts) / len(verts)
    candidates = [
        (int(round(cx)), int(round(cy))),
        (int(cx), int(cy)),
    ]
    for gx, gy in candidates:
        if (gx, gy) in heightmap.surface_z and (gx, gy) not in shoreline:
            if point_in_polygon(gx + 0.5, gy + 0.5, verts):
                return (gx, gy)
        for n in _neighbors4(gx, gy):
            if n not in heightmap.surface_z or n in shoreline:
                continue
            if point_in_polygon(n[0] + 0.5, n[1] + 0.5, verts):
                return n
    return None


def _resolve_interior(
    heightmap: SurfaceHeightmap,
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    shoreline: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    interior = interior_cells(heightmap, segments, shoreline)
    if interior:
        return interior
    seed = _interior_seed(heightmap, segments, shoreline)
    if seed is None:
        return set()
    filled: set[tuple[int, int]] = {seed}
    from app.application.worldData.generators.hydrology.geom.polygonInterior import (
        point_in_polygon,
        polygon_vertices,
    )

    verts = polygon_vertices(segments)
    queue: deque[tuple[int, int]] = deque([seed])
    while queue:
        cell = queue.popleft()
        for n in _neighbors4(*cell):
            if n in filled or n not in heightmap.surface_z or n in shoreline:
                continue
            if not point_in_polygon(n[0] + 0.5, n[1] + 0.5, verts):
                continue
            filled.add(n)
            queue.append(n)
    return filled


def _interior_distances(
    interior: set[tuple[int, int]],
    shoreline: set[tuple[int, int]],
) -> dict[tuple[int, int], int]:
    dist: dict[tuple[int, int], int] = {}
    queue: deque[tuple[tuple[int, int], int]] = deque()
    for cell in shoreline:
        for n in _neighbors4(*cell):
            if n in interior and n not in shoreline:
                queue.append((n, 1))
    while queue:
        cell, d = queue.popleft()
        if cell in dist:
            continue
        dist[cell] = d
        for n in _neighbors4(*cell):
            if n in dist or n not in interior or n in shoreline:
                continue
            queue.append((n, d + 1))
    return dist


def _shoreline_ring(
    interior: set[tuple[int, int]],
    heightmap: SurfaceHeightmap,
) -> set[tuple[int, int]]:
    ring: set[tuple[int, int]] = set()
    for cell in interior:
        for n in _neighbors4(*cell):
            if n not in interior and n in heightmap.surface_z:
                ring.add(cell)
                break
    return ring


def carve_lake_interior(
    heightmap: SurfaceHeightmap,
    interior: set[tuple[int, int]],
    bands,
    *,
    open_role: HydrologyCellRole = HydrologyCellRole.LAKE,
) -> dict[tuple[int, int], MapCellHydrology]:
    if not interior:
        return {}

    shoreline = _shoreline_ring(interior, heightmap)
    if not shoreline:
        shoreline = set(interior)

    land_shore = _land_shore_outside(shoreline, interior, heightmap)
    interior_dist = _interior_distances(interior, shoreline)
    if interior == shoreline or not interior_dist:
        interior_dist = {cell: 1 for cell in interior}
    shelf_depth = _lake_shelf_depth(bands, interior_dist)

    rim_z = max(
        (heightmap.surface_z[c] for c in land_shore),
        default=max(heightmap.surface_z[c] for c in shoreline),
    )
    floor_z = max(0, rim_z - shelf_depth - 1)

    by_cell: dict[tuple[int, int], MapCellHydrology] = {}
    for cell in land_shore:
        by_cell[cell] = MapCellHydrology(
            role=HydrologyCellRole.SHORE,
            deepening_index=0,
        )

    for cell, distance in interior_dist.items():
        if distance <= shelf_depth:
            heightmap.surface_z[cell] = max(floor_z, rim_z - distance)
            by_cell[cell] = MapCellHydrology(
                role=HydrologyCellRole.SHORE,
                deepening_index=distance,
            )
        else:
            heightmap.surface_z[cell] = floor_z
            by_cell[cell] = MapCellHydrology(role=open_role)

    return by_cell


def carve_lake_basin(
    heightmap: SurfaceHeightmap,
    spec: LakeSpec,
    bands,
) -> dict[tuple[int, int], MapCellHydrology]:
    segments = spec.shoreline_segments
    shoreline = rasterize_segments(segments)
    if not shoreline:
        return {}

    interior = _resolve_interior(heightmap, segments, shoreline)
    if not interior and shoreline:
        # Degenerate declare contour collapsed to grid lines (fixture moon lake).
        interior = set(shoreline)
    if not interior:
        return {}

    return carve_lake_interior(
        heightmap,
        interior,
        bands,
        open_role=spec.open_water_role,
    )


def _merge_bbox(
    cells: dict[tuple[int, int], MapCellHydrology],
    prev: GridBBox | None,
) -> GridBBox | None:
    if not cells:
        return prev
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    box = GridBBox(min(xs), max(xs), min(ys), max(ys))
    if prev is None:
        return box
    return GridBBox(
        min(prev.x_min, box.x_min),
        max(prev.x_max, box.x_max),
        min(prev.y_min, box.y_min),
        max(prev.y_max, box.y_max),
    )


def generate_lakes(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology] | None = None,
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    bands = resolve_hydrology_bands("lakes", world, world_uid=master.world_uid)
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    dirty: GridBBox | None = None
    occupied_cells = occupied or {}

    for spec in master.declared_lake_specs:
        carved = carve_lake_basin(heightmap, spec, bands)
        merged.update(carved)
        dirty = _merge_bbox(carved, dirty)

    lakes_policy = lakes_autoresolve_policy(world)
    if lakes_policy.lakes_enabled and lakes_policy.autoresolve:
        from app.application.worldData.generators.hydrology.autoresolve.proceduralLakeAutoresolve import (
            autoresolve_lakes,
        )

        auto, auto_bbox = autoresolve_lakes(
            world,
            heightmap,
            master,
            {**occupied_cells, **merged},
        )
        merged.update(auto)
        dirty = _merge_bbox(auto, dirty)

    return merged, dirty
