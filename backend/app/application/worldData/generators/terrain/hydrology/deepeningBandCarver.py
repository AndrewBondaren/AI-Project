"""U15 shore + deepening bands from declare coastline — D HY-2."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.hydrology.polylineRasterize import rasterize_segments
from app.application.worldData.generators.terrain.hydrology.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.terrain.hydrology.types import HydrologyBands
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def _neighbors4(gx: int, gy: int) -> list[tuple[int, int]]:
    return [(gx + 1, gy), (gx - 1, gy), (gx, gy + 1), (gx, gy - 1)]


def compute_land_centroid(heightmap: SurfaceHeightmap) -> tuple[float, float]:
    if not heightmap.surface_z:
        return (0.0, 0.0)
    sx = sy = sw = 0.0
    for (gx, gy), z in heightmap.surface_z.items():
        w = float(max(z, 1))
        sx += gx * w
        sy += gy * w
        sw += w
    if sw <= 0:
        keys = list(heightmap.surface_z.keys())
        return (
            sum(k[0] for k in keys) / len(keys),
            sum(k[1] for k in keys) / len(keys),
        )
    return (sx / sw, sy / sw)


def _dist2(cell: tuple[int, int], centroid: tuple[float, float]) -> float:
    return (cell[0] - centroid[0]) ** 2 + (cell[1] - centroid[1]) ** 2


def water_step_from_segment(
    a: tuple[int, int],
    b: tuple[int, int],
    land_centroid: tuple[float, float],
) -> tuple[int, int]:
    mx = (a[0] + b[0]) / 2
    my = (a[1] + b[1]) / 2
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if dx == 0 and dy == 0:
        return (0, 0)
    raw = [(-dy, dx), (dy, -dx)]
    steps: list[tuple[int, int]] = []
    for px, py in raw:
        sx = 0 if px == 0 else (1 if px > 0 else -1)
        sy = 0 if py == 0 else (1 if py > 0 else -1)
        if (sx, sy) != (0, 0):
            steps.append((sx, sy))
    if not steps:
        return (0, 0)
    return max(steps, key=lambda step: _dist2((mx + step[0], my + step[1]), land_centroid))


def water_side_seeds(
    coastline_cells: set[tuple[int, int]],
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    heightmap: SurfaceHeightmap,
    land_centroid: tuple[float, float],
) -> set[tuple[int, int]]:
    """Grid cells on the water side of the declare polyline."""
    seeds: set[tuple[int, int]] = set()
    segment_steps: dict[tuple[int, int], tuple[int, int]] = {}
    for a, b in segments:
        step = water_step_from_segment(a, b, land_centroid)
        for cell in rasterize_segments([(a, b)]):
            if step != (0, 0):
                segment_steps[cell] = step

    for cell in coastline_cells:
        step = segment_steps.get(cell, (0, 0))
        if step != (0, 0):
            n = (cell[0] + step[0], cell[1] + step[1])
            if n in heightmap.surface_z:
                seeds.add(n)
            continue
        for n in _neighbors4(*cell):
            if n not in heightmap.surface_z or n in coastline_cells:
                continue
            if _dist2(n, land_centroid) > _dist2(cell, land_centroid):
                seeds.add(n)
    return seeds


def _land_shore_cells(
    coastline_cells: set[tuple[int, int]],
    heightmap: SurfaceHeightmap,
    land_centroid: tuple[float, float],
) -> set[tuple[int, int]]:
    land: set[tuple[int, int]] = set()
    for cell in coastline_cells:
        if cell not in heightmap.surface_z:
            continue
        for n in _neighbors4(*cell):
            if n not in heightmap.surface_z or n in coastline_cells:
                continue
            if _dist2(n, land_centroid) < _dist2(cell, land_centroid):
                land.add(n)
    return land


def _water_gy_direction(
    coastline_cells: set[tuple[int, int]],
    land_centroid: tuple[float, float],
) -> int:
    """Grid y step toward open water: -1 = north (decreasing gy), +1 = south."""
    coast_gy = sum(c[1] for c in coastline_cells) / len(coastline_cells)
    return -1 if land_centroid[1] > coast_gy else 1


def flood_water_side(
    heightmap: SurfaceHeightmap,
    coastline_cells: set[tuple[int, int]],
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
) -> dict[tuple[int, int], int]:
    """BFS distance from coastline into water-side component (1-based)."""
    land_centroid = compute_land_centroid(heightmap)
    land_shore = _land_shore_cells(coastline_cells, heightmap, land_centroid)
    water_gy_dir = _water_gy_direction(coastline_cells, land_centroid)
    coast_gy_min = min(c[1] for c in coastline_cells)
    coast_gy_max = max(c[1] for c in coastline_cells)
    coast_gx_min = min(c[0] for c in coastline_cells)
    coast_gx_max = max(c[0] for c in coastline_cells)
    seeds = water_side_seeds(coastline_cells, segments, heightmap, land_centroid)
    dist: dict[tuple[int, int], int] = {}
    queue: deque[tuple[tuple[int, int], int]] = deque((seed, 1) for seed in seeds)

    def _in_water_strip(cell: tuple[int, int]) -> bool:
        gx, gy = cell
        if gx < coast_gx_min or gx > coast_gx_max:
            return False
        if water_gy_dir < 0:
            return gy < coast_gy_min
        if water_gy_dir > 0:
            return gy > coast_gy_max
        return True

    while queue:
        cell, d = queue.popleft()
        if cell in dist or cell not in heightmap.surface_z:
            continue
        if cell in coastline_cells or cell in land_shore:
            continue
        if not _in_water_strip(cell):
            continue
        dist[cell] = d
        for n in _neighbors4(*cell):
            if n in dist or n not in heightmap.surface_z:
                continue
            if n in coastline_cells or n in land_shore:
                continue
            if not _in_water_strip(n):
                continue
            queue.append((n, d + 1))
    return dist


def _shelf_depth(bands: HydrologyBands, water_dist: dict[tuple[int, int], int]) -> int:
    if not water_dist:
        return bands.max
    max_d = max(water_dist.values())
    if max_d <= 1:
        return bands.min
    return min(bands.max, max(max_d - 1, bands.min))


@dataclass
class DeepeningCarveResult:
    by_cell: dict[tuple[int, int], MapCellHydrology]
    dirty_bbox: GridBBox | None


def carve_deepening_bands(
    heightmap: SurfaceHeightmap,
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    bands: HydrologyBands,
    *,
    z_sea: int | None = None,
) -> DeepeningCarveResult:
    """
    U15: shoreline → deepening bands → open coastal_sea at z_sea.

    Mutates ``heightmap.surface_z`` in place.
    """
    level = resolve_z_sea(None) if z_sea is None else z_sea
    coastline_cells = rasterize_segments(segments)
    if not coastline_cells:
        return DeepeningCarveResult(by_cell={}, dirty_bbox=None)

    water_dist = flood_water_side(heightmap, coastline_cells, segments)
    land_centroid = compute_land_centroid(heightmap)
    land_shore = _land_shore_cells(coastline_cells, heightmap, land_centroid)
    by_cell: dict[tuple[int, int], MapCellHydrology] = {}
    xs: list[int] = []
    ys: list[int] = []

    for cell in land_shore:
        by_cell[cell] = MapCellHydrology(
            role=HydrologyCellRole.SHORE,
            deepening_index=0,
        )
        xs.append(cell[0])
        ys.append(cell[1])

    shelf_depth = _shelf_depth(bands, water_dist)
    for cell, distance in water_dist.items():
        xs.append(cell[0])
        ys.append(cell[1])
        if distance <= shelf_depth:
            deepening = distance
            heightmap.surface_z[cell] = max(level, level + (shelf_depth - deepening + 1))
            by_cell[cell] = MapCellHydrology(
                role=HydrologyCellRole.SHORE,
                deepening_index=deepening,
            )
        else:
            heightmap.surface_z[cell] = level
            by_cell[cell] = MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA)

    dirty = None
    if xs and ys:
        dirty = GridBBox(min(xs), max(xs), min(ys), max(ys))
    return DeepeningCarveResult(by_cell=by_cell, dirty_bbox=dirty)
