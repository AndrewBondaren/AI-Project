"""Preserve authored identity and failed intents before geometry can be dropped."""

from dataclasses import dataclass, replace
from collections.abc import Sequence

from app.application.worldData.generators.coordinates.convert import (
    fine_to_grid_xy, grid_tile_origin_x, grid_tile_origin_y, map_cell_fine_span,
)
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import segments_from_declared
from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import resolve_declared_river_intents
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.types import HydrologyMasterInput, RiverSegment, RiverTypeClassify
from app.application.worldData.generators.hydrology.waterBodyIdentity import AutoWaterBodyRole, water_body_uid_for
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.declaredRiver import HydrologyMouth
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Connection
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverRouting import RiverRoutingFailure as Failure
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True)
class RiverRouteRequest:
    object_uid: str
    object_type: Connection
    segments: tuple[RiverSegment, ...]
    source: Coord | None
    target: Coord | None
    requested_mouth: HydrologyMouth | None
    initial_failure: Failure | None = None


def diagnostic_cell(world: World, cell: Coord | None, space: CoordinateSpace) -> Coord | None:
    if cell is None or space is CoordinateSpace.WORLD_FINE_GRID:
        return cell
    span = map_cell_fine_span(world)
    return int(grid_tile_origin_x(cell[0], span)), int(grid_tile_origin_y(cell[1], span))


def request_from_segments(world: World, segments: Sequence[RiverSegment],
                          occupied: dict[Coord, MapCellHydrology], *,
                          space: CoordinateSpace) -> RiverRouteRequest:
    first, last = segments[0], segments[-1]
    source = first.polyline_cells[0] if first.polyline_cells else None
    target = last.polyline_cells[-1] if last.polyline_cells else None
    uid = first.location_uid or first.edge_uid
    if uid is None:
        if source is None:
            raise ValueError("river request has neither identity nor source")
        uid = water_body_uid_for(None, AutoWaterBodyRole.RIVER, source)
    target_fine = diagnostic_cell(world, target, space)
    entry = occupied.get(target) if target is not None else None
    target_uid = entry.water_body_uid if entry is not None and is_river_mouth(target, {}, occupied) else None
    mouth = HydrologyMouth(location_uid=target_uid, x=target_fine[0], y=target_fine[1]) if target_fine else None
    return RiverRouteRequest(uid, Connection(first.connection_type), tuple(segments), source, target, mouth)


def declared_river_requests(world: World, heightmap: SurfaceHeightmap, master: HydrologyMasterInput,
                            locations: Sequence[NamedLocation], occupied: dict[Coord, MapCellHydrology],
                            type_classify: RiverTypeClassify, topology: WorldTopology) -> list[RiverRouteRequest]:
    groups: dict[str, list[RiverSegment]] = {}
    raw_sources = {}
    raw_targets = {}
    for edge, segment in zip(master.declared_river_edges,
                             segments_from_declared(master.declared_river_edges, topology=topology), strict=True):
        request = request_from_segments(world, (segment,), occupied, space=CoordinateSpace.WORLD_SURFACE_GRID)
        groups.setdefault(request.object_uid, []).append(segment)
        raw_sources.setdefault(request.object_uid, topology.canonicalize(*edge.segment[0]))
        raw_targets[request.object_uid] = edge.segment[1]
    requests = []
    for uid, group in groups.items():
        request = request_from_segments(world, group, occupied, space=CoordinateSpace.WORLD_SURFACE_GRID)
        raw_target = raw_targets[uid]
        fine_target = diagnostic_cell(world, raw_target, CoordinateSpace.WORLD_SURFACE_GRID)
        mouth = HydrologyMouth(location_uid=request.requested_mouth.location_uid if request.requested_mouth else None,
                               x=fine_target[0], y=fine_target[1])
        requests.append(replace(request, source=raw_sources[uid],
                                target=topology.canonicalize(*raw_target), requested_mouth=mouth))
    loc_map = {location.location_uid: location for location in locations}
    span = map_cell_fine_span(world)

    def anchor(uid: str) -> Coord | None:
        location = loc_map.get(uid)
        if location is None or location.map_x is None or location.map_y is None:
            return None
        return int(location.map_x), int(location.map_y)

    for river in master.declared_river_intents:
        if river.system_role is RiverSystemRole.SYSTEM:
            continue
        failure = None
        if river.declare_mode is RiverDeclareMode.ENDPOINTS:
            source_fine = (river.source.x, river.source.y) if river.source is not None else None
            mouth = river.mouth
            target_fine = (anchor(mouth.location_uid) if mouth and mouth.location_uid
                           else (mouth.x, mouth.y) if mouth is not None else None)
            if target_fine is None or source_fine is None:
                failure = Failure.MISSING_ANCHOR
        else:
            anchors = [anchor(uid) for uid in river.route_location_uids]
            source_fine = anchors[0] if anchors else None
            target_fine = anchors[-1] if anchors else None
            mouth = HydrologyMouth(location_uid=river.route_location_uids[-1]) if anchors else None
            if not anchors or any(cell is None for cell in anchors):
                failure = Failure.MISSING_ANCHOR
        source = topology.canonicalize(*fine_to_grid_xy(*source_fine, span)) if source_fine else None
        target = topology.canonicalize(*fine_to_grid_xy(*target_fine, span)) if target_fine else None
        segments = () if failure else tuple(resolve_declared_river_intents(
            world, heightmap, [river], list(locations), occupied, type_classify,
            space=CoordinateSpace.WORLD_SURFACE_GRID, topology=topology))
        kind = Connection(segments[0].connection_type) if segments else Connection.RIVER
        requests.append(RiverRouteRequest(river.location_uid, kind, segments, source, target, mouth,
                                          failure or (Failure.MISSING_GEOMETRY if not segments else None)))
    return requests
