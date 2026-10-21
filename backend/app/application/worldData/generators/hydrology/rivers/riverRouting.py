"""Read-only route validation and deterministic reachable-water search."""

from collections import deque
from dataclasses import dataclass
from collections.abc import Sequence

from app.application.worldData.generators.hydrology.rivers.riverGeometry import river_turn_ok
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
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


def receiver_kind(cell: Coord, occupied: dict[Coord, MapCellHydrology],
                   bodies: Sequence[WaterBody]) -> BasinKind | None:
    entry = occupied[cell]
    for body in bodies:
        if body.water_body_uid == entry.water_body_uid:
            return body.kind
    return {Role.COASTAL_SEA: BasinKind.SEA, Role.OPEN_OCEAN: BasinKind.OCEAN,
            Role.INLAND_SEA: BasinKind.INLAND_SEA, Role.LAKE: BasinKind.LAKE}.get(entry.role)


def _step_failure(previous: Coord, cell: Coord, path: Sequence[Coord], heightmap: SurfaceHeightmap,
                   occupied: dict[Coord, MapCellHydrology], topology: WorldTopology) -> Failure | None:
    if cell not in heightmap.surface_z:
        return Failure.MISSING_TERRAIN
    if cell not in canonical_neighbors8(topology, previous):
        return Failure.DISCONNECTED_PATH
    if not river_turn_ok(topology, list(path[-2:]), cell):
        return Failure.TURN_LIMIT
    entry = occupied.get(cell)
    if entry is not None and entry.role is Role.RIVER_BED:
        return Failure.BLOCKED
    receiving = is_river_mouth(cell, heightmap.surface_z, occupied)
    z = entry.z_water_level if receiving and entry.z_water_level is not None else heightmap.surface_z[cell]
    if z > heightmap.surface_z[previous]:
        return Failure.UPHILL
    return None


def validate_route(request: RiverRouteRequest, heightmap: SurfaceHeightmap,
                    occupied: dict[Coord, MapCellHydrology], topology: WorldTopology,
                    policy: HydrologyRiversPolicy) -> RouteCheck:
    if request.source is None or request.source not in heightmap.surface_z:
        return RouteCheck((), Failure.MISSING_TERRAIN, request.source)
    if is_river_mouth(request.source, heightmap.surface_z, occupied):
        return RouteCheck((), Failure.SOURCE_IN_WATER, request.source)
    if occupied.get(request.source) is not None and occupied[request.source].role is Role.RIVER_BED:
        return RouteCheck((), Failure.BLOCKED, request.source)
    if request.initial_failure is not None:
        return RouteCheck((), request.initial_failure, request.target)
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
                failure = _step_failure(path[-1], cell, path, heightmap, occupied, topology)
                if failure:
                    return RouteCheck((), failure, cell)
            path.append(cell)
            if len(path) > policy.max_path_cells:
                return RouteCheck((), Failure.PATH_LIMIT, cell)
            if is_river_mouth(cell, heightmap.surface_z, occupied):
                target_uid = request.requested_mouth.location_uid if request.requested_mouth else None
                if target_uid and occupied[cell].water_body_uid != target_uid:
                    return RouteCheck((), Failure.WRONG_BODY, cell)
                return RouteCheck(tuple(path))
    return RouteCheck((), Failure.DRY_MOUTH, path[-1] if path else request.source)


def fallback_route(request: RiverRouteRequest, heightmap: SurfaceHeightmap,
                    occupied: dict[Coord, MapCellHydrology], topology: WorldTopology,
                    policy: HydrologyRiversPolicy, bodies: Sequence[WaterBody]) -> tuple[Coord, ...]:
    """BFS over directed states retains distinct approach directions to a cell."""
    source = request.source
    if source is None or source not in heightmap.surface_z or is_river_mouth(source, heightmap.surface_z, occupied):
        return ()
    if occupied.get(source) is not None and occupied[source].role is Role.RIVER_BED:
        return ()
    origin = request.target if request.target is not None else source
    initial = (None, source)
    parents = {initial: None}
    lengths = {initial: 1}
    queue = deque([initial])
    mouths = []
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
            if _step_failure(cell, neighbor, turn_path, heightmap, occupied, topology):
                continue
            parents[next_state] = state
            lengths[next_state] = lengths[state] + 1
            if is_river_mouth(neighbor, heightmap.surface_z, occupied):
                entry = occupied[neighbor]
                if entry.water_body_uid and receiver_kind(neighbor, occupied, bodies) is not None:
                    rank = (dist2(topology, origin, neighbor), neighbor[1], neighbor[0], entry.water_body_uid)
                    mouths.append((rank, next_state))
                continue
            queue.append(next_state)
    if not mouths:
        return ()
    state = min(mouths, key=lambda candidate: candidate[0])[1]
    path = []
    while state is not None:
        path.append(state[1])
        state = parents[state]
    return tuple(reversed(path))
