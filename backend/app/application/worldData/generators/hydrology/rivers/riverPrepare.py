"""Prepare one river atomically on the pre-bed snapshot, without writing z."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from app.application.jsonValidation.resolve import ResolveContext, ResolveMode
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_spec
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest, diagnostic_cell
from app.application.worldData.generators.hydrology.rivers.riverRouting import fallback_route, receiver_kind, validate_route
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverRouting import RiverRouteDiagnostic, RiverRoutingCode as Code, RiverRoutingFailure as Failure
from app.dataModel.hydrology.rivers import HydrologyRiversPolicy
from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.db.models.world import World


@dataclass(frozen=True)
class PreparedRiver:
    segments: tuple[RiverSegment, ...] = ()
    specs: tuple[RiverBedSpec, ...] = ()
    diagnostics: tuple[RiverRouteDiagnostic, ...] = ()


def _selected_segments(request: RiverRouteRequest, path: tuple[Coord, ...], redirected: bool) -> tuple[RiverSegment, ...]:
    if redirected:
        template = request.segments[0] if request.segments else RiverSegment(
            [], request.object_type.value, location_uid=request.object_uid)
        return (replace(template, polyline_cells=list(path)),)
    result = []
    for segment in request.segments:
        cells = []
        for cell in segment.polyline_cells:
            cells.append(cell)
            if cell == path[-1]:
                break
        if len(cells) > 1:
            result.append(replace(segment, polyline_cells=cells))
        if cells and cells[-1] == path[-1]:
            break
    return tuple(result)


def prepare_river(world: World, heightmap: SurfaceHeightmap, request: RiverRouteRequest,
                   occupied: dict[Coord, MapCellHydrology], topology: WorldTopology,
                   policy: HydrologyRiversPolicy, bodies: Sequence[WaterBody],
                   ctx: ResolveContext, z_min: int) -> PreparedRiver:
    checked = validate_route(request, heightmap, occupied, topology, policy)
    path = checked.path
    diagnostics = ()
    if checked.failure is not None:
        wet = any(is_river_mouth(cell, heightmap.surface_z, occupied) for cell in occupied)
        invalid_source = request.source is None or request.source not in heightmap.surface_z or (
            request.source is not None and is_river_mouth(request.source, heightmap.surface_z, occupied))
        if invalid_source:
            code = Code.INVALID_SOURCE
        elif not wet:
            code = Code.NO_REACHABLE_WATER if bodies else Code.NO_WATER_BODIES
        elif ctx.validate_only or ctx.mode is not ResolveMode.RUNTIME:
            code = Code.TARGET_UNREACHABLE
        else:
            path = fallback_route(request, heightmap, occupied, topology, policy, bodies)
            code = Code.REDIRECTED if path else Code.NO_REACHABLE_WATER
        receiving = occupied[path[-1]] if path and code is Code.REDIRECTED else None
        diagnostic = RiverRouteDiagnostic(
            world_uid=world.world_uid, object_uid=request.object_uid, object_type=request.object_type,
            requested_mouth=request.requested_mouth, code=code, reason=checked.failure,
            source_cell=diagnostic_cell(world, request.source, CoordinateSpace.WORLD_SURFACE_GRID),
            failure_cell=diagnostic_cell(world, checked.failure_cell, CoordinateSpace.WORLD_SURFACE_GRID),
            receiver_uid=receiving.water_body_uid if receiving else None,
            receiver_kind=receiver_kind(path[-1], occupied, bodies) if receiving else None,
            receiver_cell=diagnostic_cell(world, path[-1], CoordinateSpace.WORLD_SURFACE_GRID) if receiving else None,
            receiver_level=receiving.z_water_level if receiving else None,
        )
        diagnostics = (diagnostic,)
        if code is not Code.REDIRECTED:
            return PreparedRiver(diagnostics=diagnostics)
    segments = _selected_segments(request, path, bool(diagnostics))
    specs, accepted = [], []
    for segment in segments:
        spec = river_bed_spec(heightmap, segment,
            depth_step=policy.channel_depth_for(HydrologyConnectionType(segment.connection_type)),
            z_min=z_min, occupied=occupied)
        if spec.bed_z:
            accepted.append(segment)
            specs.append(spec)
    if not specs:
        # A valid river must have at least one land bed cell before its receiver.
        diagnostic = RiverRouteDiagnostic(world_uid=world.world_uid, object_uid=request.object_uid,
            object_type=request.object_type, requested_mouth=request.requested_mouth,
            code=Code.INVALID_SOURCE, reason=Failure.MISSING_GEOMETRY,
            source_cell=diagnostic_cell(world, request.source, CoordinateSpace.WORLD_SURFACE_GRID))
        return PreparedRiver(diagnostics=(diagnostic,))
    return PreparedRiver(tuple(accepted), tuple(specs), diagnostics)
