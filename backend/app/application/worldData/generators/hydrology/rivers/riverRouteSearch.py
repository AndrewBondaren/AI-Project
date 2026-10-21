"""Validate routes and search reachable receivers on a pre-bed snapshot."""

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.application.worldData.generators.hydrology.rivers.riverGeometry import river_turn_ok
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.rivers.riverReceivers import (
    drainage_index, drains_to_basin, receiver_kind,
)
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
from app.dataModel.hydrology.riverRouting import RiverRoutingFailure as Failure
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.topology.topologyGeometry import canonical_neighbors8, dist2
from app.dataModel.topology.worldTopology import Coord, WorldTopology


@dataclass(frozen=True)
class RouteCheck:
    path: tuple[Coord, ...]
    failure: Failure | None = None
    failure_cell: Coord | None = None
    invalid_source: bool = False


@dataclass(frozen=True)
class RouteSearchResult:
    path: tuple[Coord, ...] = ()
    failure: Failure | None = None


def source_failure(request: RiverRouteRequest, heightmap: SurfaceHeightmap,
                   occupied: Mapping[Coord, MapCellHydrology]) -> Failure | None:
    if request.source is None or request.source not in heightmap.surface_z:
        return Failure.MISSING_TERRAIN
    if is_river_mouth(request.source, heightmap.surface_z, occupied):
        return Failure.SOURCE_IN_WATER
    entry = occupied.get(request.source)
    return Failure.BLOCKED if entry is not None and entry.role is Role.RIVER_BED else None


def _is_receiver(cell: Coord, heightmap: SurfaceHeightmap,
                  occupied: Mapping[Coord, MapCellHydrology]) -> bool:
    entry = occupied.get(cell)
    return is_river_mouth(cell, heightmap.surface_z, occupied) or (
        entry is not None and entry.role is Role.RIVER_BED)


def _receiver_failure(cell: Coord, request: RiverRouteRequest,
                       occupied: Mapping[Coord, MapCellHydrology], bodies: Sequence[WaterBody],
                       links: Mapping[str, RiverDrainageLink]) -> Failure | None:
    entry = occupied[cell]
    if not entry.water_body_uid or receiver_kind(cell, occupied, bodies) is None:
        return Failure.RECEIVER_METADATA
    if entry.role is Role.RIVER_BED:
        if entry.water_body_uid == request.object_uid:
            return Failure.DRAINAGE_CYCLE
        if not drains_to_basin(entry.water_body_uid, links, excluding=request.object_uid):
            return Failure.RECEIVER_METADATA
    return None


def _step_failure(previous: Coord, cell: Coord, path: Sequence[Coord], heightmap: SurfaceHeightmap,
                   occupied: Mapping[Coord, MapCellHydrology], topology: WorldTopology, *,
                   allow_river: bool) -> Failure | None:
    if cell not in heightmap.surface_z:
        return Failure.MISSING_TERRAIN
    if cell not in canonical_neighbors8(topology, previous):
        return Failure.DISCONNECTED_PATH
    if not river_turn_ok(topology, list(path[-2:]), cell):
        return Failure.TURN_LIMIT
    entry = occupied.get(cell)
    if entry is not None and entry.role is Role.RIVER_BED and not allow_river:
        return Failure.BLOCKED
    receiving = is_river_mouth(cell, heightmap.surface_z, occupied)
    z = entry.z_water_level if receiving and entry.z_water_level is not None else heightmap.surface_z[cell]
    return Failure.UPHILL if z > heightmap.surface_z[previous] else None


def validate_route(request: RiverRouteRequest, heightmap: SurfaceHeightmap,
                    occupied: Mapping[Coord, MapCellHydrology], topology: WorldTopology,
                    policy: HydrologyRiversPolicy, bodies: Sequence[WaterBody]) -> RouteCheck:
    if request.initial_failure is not None:
        return RouteCheck((), request.initial_failure, request.target)
    failure = source_failure(request, heightmap, occupied)
    if failure is not None:
        return RouteCheck((), failure, request.source, invalid_source=True)
    links = drainage_index(occupied)
    path = []
    for segment in request.segments:
        cells = segment.polyline_cells
        if not cells:
            return RouteCheck((), Failure.MISSING_GEOMETRY)
        if path and cells[0] != path[-1]:
            return RouteCheck((), Failure.DISCONNECTED_PATH, cells[0])
        for cell in cells:
            if path and cell == path[-1]:
                continue
            if not path:
                if cell != request.source:
                    return RouteCheck((), Failure.DISCONNECTED_PATH, cell)
            else:
                failure = _step_failure(path[-1], cell, path, heightmap, occupied, topology,
                                        allow_river=cell == request.target)
                if failure is not None:
                    return RouteCheck((), failure, cell)
            path.append(cell)
            if len(path) > policy.max_path_cells:
                return RouteCheck((), Failure.PATH_LIMIT, cell)
            if _is_receiver(cell, heightmap, occupied):
                entry = occupied[cell]
                if request.requested_receiver_uid and entry.water_body_uid != request.requested_receiver_uid:
                    return RouteCheck((), Failure.WRONG_BODY, cell)
                failure = _receiver_failure(cell, request, occupied, bodies, links)
                return RouteCheck(tuple(path)) if failure is None else RouteCheck((), failure, cell)
    return RouteCheck((), Failure.DRY_MOUTH, path[-1] if path else request.source)


def fallback_route(request: RiverRouteRequest, heightmap: SurfaceHeightmap,
                    occupied: Mapping[Coord, MapCellHydrology], topology: WorldTopology,
                    policy: HydrologyRiversPolicy, bodies: Sequence[WaterBody]) -> RouteSearchResult:
    """BFS over directed approaches; ancestry scan is O(depth) per state.

    The path budget bounds depth. Receivers are terminal and never queued for
    transit, including incomplete candidates; only reachable metadata failures
    affect the final failure. Successful alternatives take precedence.
    """
    failure = source_failure(request, heightmap, occupied)
    if failure is not None:
        return RouteSearchResult(failure=failure)
    links = drainage_index(occupied)
    source = request.source
    origin = request.target if request.target is not None else source
    initial = (None, source)
    parents = {initial: None}
    lengths = {initial: 1}
    queue = deque([initial])
    mouths = []
    missing_metadata = False
    while queue:
        state = queue.popleft()
        previous, cell = state
        if lengths[state] >= policy.max_path_cells:
            continue
        ancestry = set()
        parent = state
        while parent is not None:
            ancestry.add(parent[1])
            parent = parents[parent]
        turn_path = [previous, cell] if previous is not None else [cell]
        for neighbor in canonical_neighbors8(topology, cell):
            next_state = (cell, neighbor)
            if next_state in parents or neighbor in ancestry:
                continue
            if _step_failure(cell, neighbor, turn_path, heightmap, occupied, topology, allow_river=True):
                continue
            parents[next_state] = state
            lengths[next_state] = lengths[state] + 1
            if _is_receiver(neighbor, heightmap, occupied):
                failure = _receiver_failure(neighbor, request, occupied, bodies, links)
                if failure is None:
                    entry = occupied[neighbor]
                    rank = (dist2(topology, origin, neighbor), neighbor[1], neighbor[0], entry.water_body_uid)
                    mouths.append((rank, next_state))
                elif failure is Failure.RECEIVER_METADATA:
                    missing_metadata = True
                continue
            queue.append(next_state)
    if not mouths:
        return RouteSearchResult(failure=Failure.RECEIVER_METADATA if missing_metadata else None)
    state = min(mouths, key=lambda candidate: candidate[0])[1]
    path = []
    while state is not None:
        path.append(state[1])
        state = parents[state]
    return RouteSearchResult(tuple(reversed(path)))
