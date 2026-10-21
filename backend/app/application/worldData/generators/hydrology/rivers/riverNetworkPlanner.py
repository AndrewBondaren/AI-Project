"""D8 river descent planner — sources → liquid mouth — D HY-5c."""

from __future__ import annotations

from typing import Any

from app.application.worldData.generators.climate.math import world_seed
from app.application.worldData.generators.hydrology.rivers.riverGeometry import distance_to_mouths, river_turn_ok
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.dataModel.topology.topologyGeometry import canonical_neighbors8, dist2
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.application.jsonValidation.worldRow import hydrology

MAX_RIVERS_PER_BBOX = 8
# Fraction of post-1.4 land_z_max for source floor when policy half-cap is too high.
RIVER_SOURCE_LAND_Z_FRACTION = 0.5


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
    topology: WorldTopology,
) -> list[tuple[int, int]]:
    sources: list[tuple[tuple[int, int], int]] = []
    for cell, z in heightmap.surface_z.items():
        if z < min_z or is_river_mouth(cell, heightmap.surface_z, occupied) or _blocked_cell(cell, occupied):
            continue
        neighbor_z = [
            heightmap.surface_z[n]
            for n in canonical_neighbors8(topology, cell)
            if n in heightmap.surface_z
        ]
        if not neighbor_z:
            continue
        if z >= max(neighbor_z):
            sources.append((cell, z))
    sources.sort(key=lambda item: (-item[1], item[0]))
    return [cell for cell, _ in sources]


def _river_source_min_z(
    heightmap: SurfaceHeightmap,
    type_classify: RiverTypeClassify,
) -> int:
    """
    Grid-aware floor after Pass 1.4: ``min(policy//2, ceil(land_z_max * fraction))``.
    Depends on post-relief ``land_z_max`` (mountains raise the span).
    """
    configured = max(1, int(type_classify.mountain_min_source_z) // 2)
    if not heightmap.surface_z:
        return configured
    land_z_max = max(heightmap.surface_z.values())
    scaled = max(1, int((int(land_z_max) * RIVER_SOURCE_LAND_Z_FRACTION) + 0.999))
    return max(1, min(configured, scaled))


def find_river_sources(
    heightmap: SurfaceHeightmap,
    occupied: dict[tuple[int, int], MapCellHydrology],
    type_classify: RiverTypeClassify,
    *,
    world_uid: str,
    topology: WorldTopology,
) -> list[tuple[int, int]]:
    if not isinstance(topology, WorldTopology):
        raise TypeError("river geometry requires an explicit WorldTopology")
    min_z = _river_source_min_z(heightmap, type_classify)
    locals_ = _local_max_sources(heightmap, occupied, min_z=min_z, topology=topology)
    ordered: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for cell in locals_:
        if cell in seen or cell not in heightmap.surface_z:
            continue
        if is_river_mouth(cell, heightmap.surface_z, occupied) or _blocked_cell(cell, occupied):
            continue
        seen.add(cell)
        ordered.append(cell)
    return ordered


def plan_descent_path(
    heightmap: SurfaceHeightmap,
    source: tuple[int, int],
    occupied: dict[tuple[int, int], MapCellHydrology],
    *, topology: WorldTopology, policy: HydrologyRiversPolicy,
) -> list[tuple[int, int]]:
    if not isinstance(topology, WorldTopology):
        raise TypeError("river geometry requires an explicit WorldTopology")
    if not isinstance(policy, HydrologyRiversPolicy):
        raise TypeError("river planning requires an explicit HydrologyRiversPolicy")
    if source not in heightmap.surface_z:
        return []

    mouths = [cell for cell in occupied if is_river_mouth(cell, heightmap.surface_z, occupied)]
    distances = distance_to_mouths(topology, heightmap.surface_z, mouths)
    path: list[tuple[int, int]] = [source]
    visited = {source}
    current = source

    path_limit = policy.max_path_cells
    while len(path) < path_limit:
        if is_river_mouth(current, heightmap.surface_z, occupied):
            return path if len(path) >= 2 else []

        current_z = heightmap.surface_z[current]
        candidates: list[tuple[tuple[float, float, int, float, int, int], tuple[int, int]]] = []
        for n in canonical_neighbors8(topology, current):
            if n in visited or n not in heightmap.surface_z:
                continue
            if _blocked_cell(n, occupied) and not is_river_mouth(n, heightmap.surface_z, occupied):
                continue
            if not river_turn_ok(topology, path, n):
                continue
            nz = heightmap.surface_z[n]
            mouth_dist = distances.get(n, 0)
            axis_penalty = 0 if n[0] == current[0] or n[1] == current[1] else 1
            if is_river_mouth(n, heightmap.surface_z, occupied):
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

    if len(path) >= 2 and is_river_mouth(path[-1], heightmap.surface_z, occupied):
        return path
    return []


def plan_path_to_target(
    heightmap: SurfaceHeightmap,
    source: tuple[int, int],
    target: tuple[int, int],
    occupied: dict[tuple[int, int], MapCellHydrology],
    *, topology: WorldTopology, policy: HydrologyRiversPolicy,
) -> list[tuple[int, int]]:
    """Standalone D8 descent biased toward target; no production callers.

    May stop at an earlier receiving-water cell instead of reaching target.
    Declared intents use their own rasterization and shared route validation;
    this helper does not define their target acceptance or runtime fallback.
    """
    if not isinstance(topology, WorldTopology):
        raise TypeError("river geometry requires an explicit WorldTopology")
    if not isinstance(policy, HydrologyRiversPolicy):
        raise TypeError("river planning requires an explicit HydrologyRiversPolicy")
    if source not in heightmap.surface_z or target not in heightmap.surface_z:
        return []
    if source == target:
        return [source]

    path: list[tuple[int, int]] = [source]
    visited = {source}
    current = source

    path_limit = policy.max_path_cells
    while len(path) < path_limit:
        if current == target:
            return path if len(path) >= 2 else []
        if is_river_mouth(current, heightmap.surface_z, occupied):
            return path if len(path) >= 2 else []

        current_z = heightmap.surface_z[current]
        candidates: list[tuple[tuple[float, float, int, float, int, int], tuple[int, int]]] = []
        for n in canonical_neighbors8(topology, current):
            if n in visited or n not in heightmap.surface_z:
                continue
            if _blocked_cell(n, occupied) and n != target and not is_river_mouth(n, heightmap.surface_z, occupied):
                continue
            if not river_turn_ok(topology, path, n):
                continue
            nz = heightmap.surface_z[n]
            target_dist = dist2(topology, n, target)
            axis_penalty = 0 if n[0] == current[0] or n[1] == current[1] else 1
            if n == target:
                rank = (-2.0, target_dist, axis_penalty, 0.0, n[0], n[1])
            elif is_river_mouth(n, heightmap.surface_z, occupied):
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
    *, topology: WorldTopology,
) -> list[list[tuple[int, int]]]:
    """Return candidate polylines, not accepted materialized river segments.

    Dry SHORE may host a source or route cell; receiving water and existing
    river beds exclude sources. Interiors cannot overlap claimed cells, but
    routes may share their terminal receiving-water cell. Assembly separately
    validates requests, prepares profiles and publishes materialized segments.
    """
    if not isinstance(topology, WorldTopology):
        raise TypeError("river planning requires an explicit WorldTopology")
    world_uid = getattr(world, "world_uid", "world")
    sources = find_river_sources(heightmap, occupied, type_classify, world_uid=world_uid, topology=topology)
    if not sources:
        return []

    seed = world_seed(world)
    sources.sort(key=lambda c: (c[0] * 31 + c[1]) ^ seed)

    polylines: list[list[tuple[int, int]]] = []
    claimed = {cell for cell in occupied
               if is_river_mouth(cell, heightmap.surface_z, occupied) or _blocked_cell(cell, occupied)}

    for source in sources:
        if len(polylines) >= MAX_RIVERS_PER_BBOX:
            break
        if source in claimed:
            continue
        path = plan_descent_path(heightmap, source, occupied, topology=topology, policy=hydrology(world).default_rivers)
        if len(path) < 2:
            continue
        interior = set(path[:-1])
        if interior & claimed:
            continue
        polylines.append(path)
        claimed.update(path)

    return polylines
