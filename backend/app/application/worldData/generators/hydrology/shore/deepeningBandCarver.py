"""U15 shore + deepening bands from declare coastline — D HY-2."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import resolve_z_sea
from app.application.worldData.generators.hydrology.types import HydrologyBands
from app.application.worldData.generators.hydrology.shore.waterSideFootprint import (
    CoastlineWaterSide,
    compute_land_centroid,
    water_side_footprint,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.enums.hydrologyShoreKind import HydrologyShoreKind
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.facing import CARDINAL_FACINGS, CARDINAL_WALL_OUTWARD_DELTA, Facing
from app.dataModel.topology.topologyGeometry import dist2, unrolled_images
from app.dataModel.topology.worldTopology import WorldTopology


def water_side_seeds(
    coastline_cells: set[tuple[int, int]],
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    heightmap: SurfaceHeightmap,
    land_centroid: tuple[float, float],
    *, topology: WorldTopology,
) -> set[tuple[int, int]]:
    geometry = CoastlineWaterSide(coastline_cells, segments, land_centroid, topology=topology)
    return geometry.seeds(lambda cell: cell in heightmap.surface_z)


def _land_shore_cells(
    coastline_cells: set[tuple[int, int]],
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    heightmap: SurfaceHeightmap,
    land_centroid: tuple[float, float],
    *, topology: WorldTopology,
) -> set[tuple[int, int]]:
    geometry = CoastlineWaterSide(coastline_cells, segments, land_centroid, topology=topology)
    return geometry.land_shore(lambda cell: cell in heightmap.surface_z)


def flood_water_side(
    heightmap: SurfaceHeightmap,
    coastline_cells: set[tuple[int, int]],
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    *, topology: WorldTopology,
) -> dict[tuple[int, int], int]:
    """Reachable water side with projection inside the nearest segment."""
    geometry = CoastlineWaterSide(coastline_cells, segments,
                                 compute_land_centroid(heightmap, topology=topology), topology=topology)
    return water_side_footprint(
        geometry, bounded=True, passable=lambda cell: cell in heightmap.surface_z,
    )


def _ocean_facing(topology: WorldTopology, land_centroid: tuple[float, float]) -> Facing:
    bounds = topology.bounds
    center = (bounds.x_min + bounds.x_max) / 2, (bounds.y_min + bounds.y_max) / 2
    land = unrolled_images(topology, land_centroid, anchor=center)[0].coord
    dx, dy = center[0] - land[0], center[1] - land[1]
    if abs(dy) >= abs(dx):
        return Facing.SOUTH if dy <= 0 else Facing.NORTH
    return Facing.WEST if dx < 0 else Facing.EAST


def _on_ocean_half_plane(cell: tuple[int, int], facing: Facing,
                          land_centroid: tuple[float, float], topology: WorldTopology) -> bool:
    point = unrolled_images(topology, cell, anchor=land_centroid)[0].coord
    dx, dy = CARDINAL_WALL_OUTWARD_DELTA[facing]
    # Both positions are in the centroid's unrolled frame.
    return (point[0] - land_centroid[0]) * dx + (point[1] - land_centroid[1]) * dy > 0


def _bbox_ocean_edge_seeds(heightmap: SurfaceHeightmap, facing: Facing,
                            topology: WorldTopology) -> set[tuple[int, int]]:
    seeds: set[tuple[int, int]] = set()
    for x, y, outward in topology.bounds.edge_tiles():
        if outward is not facing or (x, y) not in heightmap.surface_z:
            continue
        seeds.add((x, y))
        neighbor = topology.neighbor(x, y, outward)
        if neighbor is not None and neighbor.coord in heightmap.surface_z:
            seeds.add(neighbor.coord)
    return seeds


def flood_from_bbox_ocean_edge(
    heightmap: SurfaceHeightmap,
    *, topology: WorldTopology,
) -> dict[tuple[int, int], int]:
    """
    Procedural v1: flood from map bbox ocean edge into land half-plane — D HY-5a no-declare.
    """
    if not heightmap.surface_z:
        return {}
    land_centroid = compute_land_centroid(heightmap, topology=topology)
    facing = _ocean_facing(topology, land_centroid)
    seeds = _bbox_ocean_edge_seeds(heightmap, facing, topology)
    if not seeds:
        return {}

    dist: dict[tuple[int, int], int] = {}
    queue: deque[tuple[tuple[int, int], int]] = deque((seed, 1) for seed in sorted(seeds))
    while queue:
        cell, d = queue.popleft()
        if cell in dist or cell not in heightmap.surface_z:
            continue
        if not _on_ocean_half_plane(cell, facing, land_centroid, topology):
            continue
        dist[cell] = d
        for neighbor_facing in CARDINAL_FACINGS:
            neighbor = topology.neighbor(*cell, neighbor_facing)
            if neighbor is None:
                continue
            n = neighbor.coord
            if n in dist or n not in heightmap.surface_z:
                continue
            queue.append((n, d + 1))
    return dist


def land_shore_from_water_dist(
    heightmap: SurfaceHeightmap,
    water_dist: dict[tuple[int, int], int],
    land_centroid: tuple[float, float],
    *, topology: WorldTopology,
) -> set[tuple[int, int]]:
    land: set[tuple[int, int]] = set()
    for cell in water_dist:
        for facing in CARDINAL_FACINGS:
            neighbor = topology.neighbor(*cell, facing)
            if neighbor is None:
                continue
            n = neighbor.coord
            if n in water_dist or n not in heightmap.surface_z:
                continue
            if dist2(topology, n, land_centroid) < dist2(topology, cell, land_centroid):
                land.add(n)
    return land


def flood_water_side_unbounded(
    heightmap: SurfaceHeightmap,
    coastline_cells: set[tuple[int, int]],
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    *, topology: WorldTopology,
) -> dict[tuple[int, int], int]:
    """Reachable water half-plane of the nearest segment, including beyond ends."""
    geometry = CoastlineWaterSide(coastline_cells, segments,
                                 compute_land_centroid(heightmap, topology=topology), topology=topology)
    return water_side_footprint(
        geometry, bounded=False, passable=lambda cell: cell in heightmap.surface_z,
    )


def declare_coastline_bbox_padded(
    segments: list[tuple[tuple[int, int], tuple[int, int]]],
    *,
    pad: int = 1,
) -> GridBBox | None:
    coastline_cells = rasterize_segments(segments)
    if not coastline_cells:
        return None
    xs = [cell[0] for cell in coastline_cells]
    ys = [cell[1] for cell in coastline_cells]
    return GridBBox(
        min(xs) - pad,
        max(xs) + pad,
        min(ys) - pad,
        max(ys) + pad,
    )


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
    topology: WorldTopology,
    water_body_uid: str,
    z_sea: int | None = None,
) -> DeepeningCarveResult:
    """
    U15: shoreline → deepening bands → open coastal_sea at z_sea.

    Mutates ``heightmap.surface_z`` in place.
    """
    level = resolve_z_sea(None) if z_sea is None else z_sea
    coastline_cells = rasterize_segments(segments, topology=topology)
    if not coastline_cells:
        return DeepeningCarveResult(by_cell={}, dirty_bbox=None)

    geometry = CoastlineWaterSide(coastline_cells, segments,
                                 compute_land_centroid(heightmap, topology=topology), topology=topology)
    footprint = water_side_footprint(
        geometry, bounded=True, passable=lambda cell: cell in heightmap.surface_z,
    )
    land_shore = geometry.land_shore(lambda cell: cell in heightmap.surface_z)
    return _apply_carve(heightmap, footprint, land_shore, bands, level, water_body_uid)


def _apply_carve(
    heightmap: SurfaceHeightmap,
    water_dist: dict[tuple[int, int], int],
    land_shore: set[tuple[int, int]],
    bands: HydrologyBands,
    level: int,
    water_body_uid: str,
) -> DeepeningCarveResult:
    """Apply the interim shelf profile to a precomputed footprint (HY-8 seam)."""
    by_cell: dict[tuple[int, int], MapCellHydrology] = {}
    xs: list[int] = []
    ys: list[int] = []

    for cell in land_shore:
        by_cell[cell] = MapCellHydrology.shore(
            HydrologyShoreKind.SEA,
            deepening_index=0,
            water_body_uid=water_body_uid,
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
            by_cell[cell] = MapCellHydrology.shore(
                HydrologyShoreKind.SEA,
                deepening_index=deepening,
                water_body_uid=water_body_uid,
            )
        else:
            heightmap.surface_z[cell] = level
            by_cell[cell] = MapCellHydrology(role=HydrologyCellRole.COASTAL_SEA,
                                             water_body_uid=water_body_uid)

    dirty = None
    if xs and ys:
        dirty = GridBBox(min(xs), max(xs), min(ys), max(ys))
    return DeepeningCarveResult(by_cell=by_cell, dirty_bbox=dirty)
