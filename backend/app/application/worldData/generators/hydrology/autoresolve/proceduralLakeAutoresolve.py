"""Procedural lake basins from terrain depression detect — D HY-5b."""

from __future__ import annotations

from collections import deque
from typing import Any

from app.application.worldData.generators.climate.anchorDetect import (
    ProminenceScale,
    detect_terrain_features,
)
from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import _neighbors4
from app.application.worldData.generators.hydrology.shore.heightmapSurfaceCells import (
    heightmap_top_surface_cells,
)
from app.application.worldData.generators.hydrology.basins.lakeBasinGenerator import (
    carve_lake_interior,
)
from app.application.worldData.generators.hydrology.load.resolveHydrologyBands import (
    resolve_hydrology_bands,
)
from app.application.worldData.generators.hydrology.types import HydrologyMasterInput
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def flood_basin_interior(
    heightmap: SurfaceHeightmap,
    center: tuple[int, int],
    blocked: set[tuple[int, int]],
    *,
    prominence: int,
    max_radius: int,
) -> set[tuple[int, int]]:
    """Grow connected depression from basin seed — bounded by spill elevation + radius."""
    if center not in heightmap.surface_z or center in blocked:
        return set()

    center_z = heightmap.surface_z[center]
    spill_z = center_z + prominence
    interior: set[tuple[int, int]] = set()
    queue: deque[tuple[tuple[int, int], int]] = deque([(center, 0)])

    while queue:
        cell, dist = queue.popleft()
        if cell in interior or cell in blocked:
            continue
        if cell not in heightmap.surface_z:
            continue
        if dist > max_radius:
            continue
        z = heightmap.surface_z[cell]
        if z > spill_z and cell != center:
            continue
        interior.add(cell)
        for n in _neighbors4(*cell):
            queue.append((n, dist + 1))
    return interior


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


def autoresolve_lakes(
    world: Any,
    heightmap: SurfaceHeightmap,
    master: HydrologyMasterInput,
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> tuple[dict[tuple[int, int], MapCellHydrology], GridBBox | None]:
    """
    Detect local basins via ``detect_terrain_features``; carve lakes not overlapping occupied cells.
    """
    cells = heightmap_top_surface_cells(heightmap)
    features = [
        feature
        for feature in detect_terrain_features(
            cells,
            master.world_uid,
            scale=ProminenceScale.GRID,
        )
        if feature.kind == "basin"
    ]
    if not features:
        return {}, None

    bands = resolve_hydrology_bands("lakes", world, world_uid=master.world_uid)
    claimed = set(occupied.keys())
    merged: dict[tuple[int, int], MapCellHydrology] = {}
    dirty: GridBBox | None = None

    for feature in features:
        center = (feature.gx, feature.gy)
        if center in claimed:
            continue

        interior = flood_basin_interior(
            heightmap,
            center,
            claimed,
            prominence=feature.prominence,
            max_radius=bands.max,
        )
        if not interior or interior & claimed:
            continue

        carved = carve_lake_interior(
            heightmap,
            interior,
            bands,
            open_role=HydrologyCellRole.LAKE,
        )
        if not carved:
            continue

        merged.update(carved)
        claimed.update(carved.keys())
        dirty = _merge_bbox(carved, dirty)

    return merged, dirty
