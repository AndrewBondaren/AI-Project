"""Order terminal confluence dependencies before preparing any relief profiles."""

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import replace

from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverRouting import RiverRoutingFailure as Failure
from app.dataModel.topology.worldTopology import Coord


def order_river_requests(requests: Sequence[RiverRouteRequest], surface_z: Mapping[Coord, int],
                          occupied: Mapping[Coord, MapCellHydrology]) -> list[RiverRouteRequest]:
    """Only terminal targets imply dependencies; crossing interiors grants no claim."""
    by_uid = {request.object_uid: request for request in requests}
    at_cell: dict[Coord, set[str]] = {}
    for request in requests:
        for segment in request.segments:
            for cell in segment.polyline_cells:
                at_cell.setdefault(cell, set()).add(request.object_uid)
    dependency, prepared = {}, {}
    for request in requests:
        uid = request.requested_receiver_uid
        if uid is None and request.target is not None and not is_river_mouth(
                request.target, surface_z, occupied):
            candidates = at_cell.get(request.target, set()) - {request.object_uid}
            if candidates:
                uid = min(candidates)
                request = replace(request, requested_receiver_uid=uid)
        prepared[request.object_uid] = request
        if uid in by_uid:
            dependency[request.object_uid] = uid
    children: dict[str, list[str]] = {}
    for uid, parent in dependency.items():
        children.setdefault(parent, []).append(uid)
    ready = deque(uid for uid in prepared if uid not in dependency)
    ordered, visited = [], set()
    while ready:
        uid = ready.popleft()
        visited.add(uid)
        ordered.append(prepared[uid])
        ready.extend(children.get(uid, ()))
    for uid, request in prepared.items():
        if uid not in visited:
            # No producer can prove a rooted drainage chain through this cycle.
            ordered.append(replace(request, initial_failure=Failure.DRAINAGE_CYCLE))
    return ordered
