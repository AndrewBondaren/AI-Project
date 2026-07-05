"""D8 river descent planner — sources → liquid mouth — D HY-5c."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.anchorDetect import detect_terrain_features
from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.terrain.hydrology.heightmapSurfaceCells import (
    heightmap_top_surface_cells,
)
from app.application.worldData.generators.terrain.hydrology.smoothRiverPolyline import step_turn_ok
from app.application.worldData.generators.terrain.hydrology.types import RiverTypeClassify
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology

MAX_RIVERS_PER_BBOX = 8
MAX_PATH_CELLS = 128


def _neighbors8(gx: int, gy: int) -> list[tuple[int, int]]:
    return [
        (gx + dx, gy + dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if dx != 0 or dy != 0
    ]


def _is_water_role(role: HydrologyCellRole | None) -> bool:
    return role is not None and role.is_open_water_role()


def _mouth_cell(
    cell: tuple[int, int],
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> bool:
    entry = occupied.get(cell)
    return entry is not None and _is_water_role(entry.role)


def _blocked_cell(
    cell: tuple[int, int],
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> bool:
    entry = occupied.get(cell)
    if entry is None:
        return False
    return entry.role == HydrologyCellRole.RIVER_BED


def _local_max_sources(
    heightmap: SurfaceHeightmap,
    occupied: dict[tuple[int, int], MapCellHydrology],
    *,
    min_z: int,
) -> list[tuple[int, int]]:
    sources: list[tuple[tuple[int, int], int]] = []
    for cell, z in heightmap.surface_z.items():
        if z < min_z or _mouth_cell(cell, occupied) or _blocked_cell(cell, occupied):
            continue
        neighbor_z = [
            heightmap.surface_z[n]
            for n in _neighbors8(*cell)
            if n in heightmap.surface_z
        ]
        if not neighbor_z:
            continue
        if z >= max(neighbor_z):
            sources.append((cell, z))
    sources.sort(key=lambda item: item[1], reverse=True)
    return [cell for cell, _ in sources]


def find_river_sources(
    heightmap: SurfaceHeightmap,
    occupied: dict[tuple[int, int], MapCellHydrology],
    type_classify: RiverTypeClassify,
    *,
    world_uid: str,
) -> list[tuple[int, int]]:
    cells = heightmap_top_surface_cells(heightmap)
    peaks = [
        (feature.gx, feature.gy)
        for feature in detect_terrain_features(cells, world_uid)
        if feature.kind == "peak"
    ]
    peak_set = set(peaks)
    min_z = max(1, type_classify.mountain_min_source_z // 2)
    locals_ = _local_max_sources(heightmap, occupied, min_z=min_z)
    ordered: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for cell in peaks + locals_:
        if cell in seen or cell not in heightmap.surface_z:
            continue
        if _mouth_cell(cell, occupied) or _blocked_cell(cell, occupied):
            continue
        seen.add(cell)
        ordered.append(cell)
    return ordered


def _mouth_cells(occupied: dict[tuple[int, int], MapCellHydrology]) -> list[tuple[int, int]]:
    return [cell for cell, entry in occupied.items() if _is_water_role(entry.role)]


def _mouth_distance(
    cell: tuple[int, int],
    mouths: list[tuple[int, int]],
) -> int:
    if not mouths:
        return 0
    gx, gy = cell
    return min(abs(gx - mx) + abs(gy - my) for mx, my in mouths)


def plan_descent_path(
    heightmap: SurfaceHeightmap,
    source: tuple[int, int],
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> list[tuple[int, int]]:
    if source not in heightmap.surface_z:
        return []

    mouths = _mouth_cells(occupied)
    path: list[tuple[int, int]] = [source]
    visited = {source}
    current = source

    while len(path) < MAX_PATH_CELLS:
        if _mouth_cell(current, occupied):
            return path if len(path) >= 2 else []

        current_z = heightmap.surface_z[current]
        candidates: list[tuple[tuple[float, int, float, int, int], tuple[int, int]]] = []
        for n in _neighbors8(*current):
            if n in visited or n not in heightmap.surface_z:
                continue
            if _blocked_cell(n, occupied) and not _mouth_cell(n, occupied):
                continue
            if not step_turn_ok(path, n):
                continue
            nz = heightmap.surface_z[n]
            mouth_dist = _mouth_distance(n, mouths)
            axis_penalty = 0 if n[0] == current[0] or n[1] == current[1] else 1
            if _mouth_cell(n, occupied):
                rank = (-1.0, mouth_dist, axis_penalty, 0.0, n[0], n[1])
            elif nz < current_z:
                rank = (0.0, mouth_dist, axis_penalty, -float(current_z - nz), n[0], n[1])
            elif nz == current_z:
                rank = (1.0, mouth_dist, axis_penalty, 0.0, n[0], n[1])
            else:
                continue
            candidates.append((rank, n))

        if not candidates:
            break
        candidates.sort(key=lambda item: item[0])
        next_cell = candidates[0][1]
        path.append(next_cell)
        visited.add(next_cell)
        current = next_cell

    if len(path) >= 2 and _mouth_cell(path[-1], occupied):
        return path
    return []


def _target_distance(cell: tuple[int, int], target: tuple[int, int]) -> int:
    return abs(cell[0] - target[0]) + abs(cell[1] - target[1])


def plan_path_to_target(
    heightmap: SurfaceHeightmap,
    source: tuple[int, int],
    target: tuple[int, int],
    occupied: dict[tuple[int, int], MapCellHydrology],
) -> list[tuple[int, int]]:
    """D8 descent biased toward a fixed mouth cell (declare endpoints/via)."""
    if source not in heightmap.surface_z or target not in heightmap.surface_z:
        return []
    if source == target:
        return [source]

    path: list[tuple[int, int]] = [source]
    visited = {source}
    current = source

    while len(path) < MAX_PATH_CELLS:
        if current == target:
            return path if len(path) >= 2 else []
        if _mouth_cell(current, occupied) and current == target:
            return path if len(path) >= 2 else []

        current_z = heightmap.surface_z[current]
        candidates: list[tuple[tuple[float, int, float, int, int], tuple[int, int]]] = []
        for n in _neighbors8(*current):
            if n in visited or n not in heightmap.surface_z:
                continue
            if _blocked_cell(n, occupied) and n != target and not _mouth_cell(n, occupied):
                continue
            if not step_turn_ok(path, n):
                continue
            nz = heightmap.surface_z[n]
            target_dist = _target_distance(n, target)
            axis_penalty = 0 if n[0] == current[0] or n[1] == current[1] else 1
            if n == target:
                rank = (-2.0, target_dist, axis_penalty, 0.0, n[0], n[1])
            elif _mouth_cell(n, occupied) and n == target:
                rank = (-1.0, target_dist, axis_penalty, 0.0, n[0], n[1])
            elif nz < current_z:
                rank = (0.0, target_dist, axis_penalty, -float(current_z - nz), n[0], n[1])
            elif nz == current_z:
                rank = (1.0, target_dist, axis_penalty, 0.0, n[0], n[1])
            else:
                continue
            candidates.append((rank, n))

        if not candidates:
            break
        candidates.sort(key=lambda item: item[0])
        next_cell = candidates[0][1]
        path.append(next_cell)
        visited.add(next_cell)
        current = next_cell

    if path[-1] == target and len(path) >= 2:
        return path
    return []


def plan_river_network(
    world: Any,
    heightmap: SurfaceHeightmap,
    occupied: dict[tuple[int, int], MapCellHydrology],
    type_classify: RiverTypeClassify,
) -> list[list[tuple[int, int]]]:
    """Return polylines (cell lists) source → mouth on liquid."""
    world_uid = getattr(world, "world_uid", "world")
    sources = find_river_sources(heightmap, occupied, type_classify, world_uid=world_uid)
    if not sources:
        return []

    seed = world_seed(world)
    sources.sort(key=lambda c: (c[0] * 31 + c[1]) ^ seed)

    polylines: list[list[tuple[int, int]]] = []
    claimed: set[tuple[int, int]] = set(occupied.keys())

    for source in sources:
        if len(polylines) >= MAX_RIVERS_PER_BBOX:
            break
        if source in claimed:
            continue
        path = plan_descent_path(heightmap, source, occupied)
        if len(path) < 2:
            continue
        interior = set(path[:-1])
        if interior & claimed:
            continue
        polylines.append(path)
        claimed.update(path)

    return polylines
