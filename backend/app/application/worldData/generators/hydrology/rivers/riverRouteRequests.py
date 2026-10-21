"""Keep authored location identity separate from resolved receiving-water identity."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from app.application.worldData.generators.coordinates.convert import (
    fine_to_grid_xy, grid_tile_origin_x, grid_tile_origin_y, map_cell_fine_span,
)
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import segments_from_declared
from app.application.worldData.generators.hydrology.rivers.resolveDeclaredRiverPath import (
    resolve_declared_river_intents, resolve_mouth_cell,
)
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.types import DeclaredRiverEdge, RiverSegment
from app.application.worldData.generators.hydrology.waterBodyIdentity import AutoWaterBodyRole, water_body_uid_for
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.declaredRiver import DeclaredRiver, HydrologyMouth
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType as Connection
from app.dataModel.hydrology.enums.riverDeclareMode import RiverDeclareMode
from app.dataModel.hydrology.enums.riverSystemRole import RiverSystemRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverRouting import RiverRoutingFailure as Failure
from app.dataModel.hydrology.rivers import RiverTypeClassify
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass(frozen=True)
class RiverRouteRequest:
    object_uid: str
    object_type: Connection | None
    segments: tuple[RiverSegment, ...]
    source: Coord | None
    target: Coord | None
    requested_mouth: HydrologyMouth | None
    initial_failure: Failure | None = None
    requested_receiver_uid: str | None = None
    rejected_connection_type: str | None = None


def diagnostic_cell(world: World, cell: Coord | None, space: CoordinateSpace) -> Coord | None:
    if cell is None or space is CoordinateSpace.WORLD_FINE_GRID:
        return cell
    span = map_cell_fine_span(world)
    return int(grid_tile_origin_x(cell[0], span)), int(grid_tile_origin_y(cell[1], span))


def segment_object_uid(segment: RiverSegment) -> str:
    if segment.location_uid or segment.edge_uid:
        return segment.location_uid or segment.edge_uid
    if not segment.polyline_cells:
        raise ValueError("river request has neither identity nor source")
    return water_body_uid_for(None, AutoWaterBodyRole.RIVER, segment.polyline_cells[0])


def _target_identity(target: Coord | None, surface_z: Mapping[Coord, int],
                     occupied: Mapping[Coord, MapCellHydrology]) -> str | None:
    entry = occupied.get(target)
    if entry is not None and (entry.role is Role.RIVER_BED or is_river_mouth(target, surface_z, occupied)):
        return entry.water_body_uid
    return None


def request_from_segments(world: World, segments: Sequence[RiverSegment],
                          occupied: Mapping[Coord, MapCellHydrology], surface_z: Mapping[Coord, int], *,
                          space: CoordinateSpace) -> RiverRouteRequest:
    first, last = segments[0], segments[-1]
    source = first.polyline_cells[0] if first.polyline_cells else None
    target = last.polyline_cells[-1] if last.polyline_cells else None
    target_fine = diagnostic_cell(world, target, space)
    mouth = HydrologyMouth(x=target_fine[0], y=target_fine[1]) if target_fine else None
    kinds = []
    for segment in segments:
        try:
            kinds.append(Connection(segment.connection_type))
        except ValueError:
            return RiverRouteRequest(segment_object_uid(first), None, tuple(segments), source, target, mouth,
                                     Failure.INVALID_CONNECTION_TYPE,
                                     _target_identity(target, surface_z, occupied), segment.connection_type)
    return RiverRouteRequest(segment_object_uid(first), kinds[0], tuple(segments), source, target, mouth,
                             requested_receiver_uid=_target_identity(target, surface_z, occupied))


def _edge_requests(world: World, heightmap: SurfaceHeightmap, edges: Sequence[DeclaredRiverEdge],
                   occupied: Mapping[Coord, MapCellHydrology], topology: WorldTopology,
                   space: CoordinateSpace) -> list[RiverRouteRequest]:
    groups: dict[str, list[RiverSegment]] = {}
    sources, targets = {}, {}
    for edge, segment in zip(edges, segments_from_declared(edges, topology=topology), strict=True):
        uid = segment_object_uid(segment)
        groups.setdefault(uid, []).append(segment)
        sources.setdefault(uid, topology.canonicalize(*edge.segment[0]))
        targets[uid] = edge.segment[1]
    requests = []
    for uid, group in groups.items():
        request = request_from_segments(world, group, occupied, heightmap.surface_z, space=space)
        target = topology.canonicalize(*targets[uid])
        fine = diagnostic_cell(world, targets[uid], space)
        requests.append(replace(request, source=sources[uid], target=target,
            requested_mouth=HydrologyMouth(x=fine[0], y=fine[1]),
            requested_receiver_uid=_target_identity(target, heightmap.surface_z, occupied)))
    return requests


def _intent_requests(world: World, heightmap: SurfaceHeightmap, intents: Sequence[DeclaredRiver],
                     locations: Sequence[NamedLocation], occupied: dict[Coord, MapCellHydrology],
                     type_classify: RiverTypeClassify, topology: WorldTopology,
                     space: CoordinateSpace, river_uids: frozenset[str],
                     candidates: Sequence[RiverSegment]) -> list[RiverRouteRequest]:
    loc_map = {location.location_uid: location for location in locations}
    span = map_cell_fine_span(world) if space is CoordinateSpace.WORLD_SURFACE_GRID else 1

    def anchor(uid: str) -> Coord | None:
        location = loc_map.get(uid)
        if location is None or location.map_x is None or location.map_y is None:
            return None
        return int(location.map_x), int(location.map_y)

    requests = []
    for river in intents:
        if river.system_role is RiverSystemRole.SYSTEM:
            continue
        river_cells = frozenset(cell for segment in candidates if segment.location_uid != river.location_uid
                                for cell in segment.polyline_cells)
        if river.declare_mode is RiverDeclareMode.ENDPOINTS:
            source_fine = (river.source.x, river.source.y) if river.source is not None else None
            mouth = river.mouth
            target_fine = (anchor(mouth.location_uid) if mouth and mouth.location_uid
                           else (mouth.x, mouth.y) if mouth is not None else None)
            missing = target_fine is None or source_fine is None
        else:
            anchors = [anchor(uid) for uid in river.route_location_uids]
            source_fine = anchors[0] if anchors else None
            target_fine = anchors[-1] if anchors else None
            mouth = HydrologyMouth(location_uid=river.route_location_uids[-1]) if anchors else None
            missing = not anchors or any(cell is None for cell in anchors)
        source = topology.canonicalize(*fine_to_grid_xy(*source_fine, span)) if source_fine else None
        target = resolve_mouth_cell(world, mouth, locations, occupied, heightmap,
                                    space=space, topology=topology, river_uids=river_uids, river_cells=river_cells) if target_fine is not None else None
        segments = () if missing else tuple(resolve_declared_river_intents(
            world, heightmap, [river], list(locations), occupied, type_classify,
            space=space, topology=topology, river_uids=river_uids, river_cells=river_cells))
        if segments:
            request = request_from_segments(world, segments, occupied, heightmap.surface_z, space=space)
            request = replace(request, object_uid=river.location_uid, source=source, target=target,
                              requested_mouth=mouth,
                              requested_receiver_uid=_target_identity(target, heightmap.surface_z, occupied))
        else:
            request = RiverRouteRequest(river.location_uid, Connection.RIVER, (), source, target, mouth,
                                        Failure.MISSING_ANCHOR if missing else Failure.MISSING_GEOMETRY)
        if mouth is not None and mouth.location_uid in river_uids:
            request = replace(request, requested_receiver_uid=mouth.location_uid)
        if river.system_role is RiverSystemRole.TRIBUTARY:
            request = replace(request, requested_receiver_uid=river.parent_location_uid)
        requests.append(request)
    return requests


def declared_river_requests(world: World, heightmap: SurfaceHeightmap,
                            edges: Sequence[DeclaredRiverEdge], intents: Sequence[DeclaredRiver],
                            locations: Sequence[NamedLocation], occupied: dict[Coord, MapCellHydrology],
                            type_classify: RiverTypeClassify, topology: WorldTopology, *,
                            space: CoordinateSpace) -> list[RiverRouteRequest]:
    edge_requests = _edge_requests(world, heightmap, edges, occupied, topology, space)
    river_uids = frozenset([edge.location_uid for edge in edges if edge.location_uid]
                          + [river.location_uid for river in intents])
    # A geometry-only prepass makes future confluence anchors visible before
    # any producer is accepted. It grants no claims or receiver metadata.
    candidates = [segment for request in edge_requests for segment in request.segments]
    candidates.extend(resolve_declared_river_intents(world, heightmap, list(intents), list(locations), {},
        type_classify, space=space, topology=topology, river_uids=river_uids))
    return [*edge_requests, *_intent_requests(world, heightmap, intents, locations, occupied,
        type_classify, topology, space, river_uids, candidates)]
