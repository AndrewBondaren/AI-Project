"""Prepare rooted drainage atomically; relief remains the sole elevation writer."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from app.application.jsonValidation.resolve import ResolveContext
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_roles, river_bed_spec
from app.application.worldData.generators.hydrology.rivers.riverReceivers import receiver_kind
from app.application.worldData.generators.hydrology.rivers.riverRequestOrder import order_river_requests
from app.application.worldData.generators.hydrology.rivers.riverRouteDiagnostics import is_runtime_river_context
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest, diagnostic_cell
from app.application.worldData.generators.hydrology.rivers.riverRouteSearch import validate_route, fallback_route
from app.application.worldData.generators.hydrology.types import RiverSegment
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole as Role
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.riverDrainageLink import RiverDrainageLink
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
    drainage: RiverDrainageLink | None = None


def _diagnostic(world: World, request: RiverRouteRequest, space: CoordinateSpace, *,
                code: Code, reason: Failure, failure_cell: Coord | None = None,
                fallback_reason: Failure | None = None, receiver: MapCellHydrology | None = None,
                cell: Coord | None = None, bodies: Sequence[WaterBody] = (),
                occupied: Mapping[Coord, MapCellHydrology] | None = None) -> RiverRouteDiagnostic:
    return RiverRouteDiagnostic(
        world_uid=world.world_uid, object_uid=request.object_uid, object_type=request.object_type,
        rejected_connection_type=request.rejected_connection_type,
        requested_mouth=request.requested_mouth, requested_receiver_uid=request.requested_receiver_uid,
        code=code, reason=reason, fallback_reason=fallback_reason,
        source_cell=diagnostic_cell(world, request.source, space),
        failure_cell=diagnostic_cell(world, failure_cell, space),
        receiver_uid=receiver.water_body_uid if receiver else None,
        receiver_kind=receiver_kind(cell, occupied, bodies) if receiver else None,
        receiver_cell=diagnostic_cell(world, cell, space) if receiver else None,
        receiver_level=receiver.z_water_level if receiver else None,
    )


def _invalid_type(world: World, request: RiverRouteRequest, space: CoordinateSpace,
                   rejected: str) -> PreparedRiver:
    request = replace(request, object_type=None, rejected_connection_type=rejected)
    return PreparedRiver(diagnostics=(_diagnostic(world, request, space,
        code=Code.INVALID_CONNECTION_TYPE, reason=Failure.INVALID_CONNECTION_TYPE),))


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
        # A one-cell classifier boundary has no length; validation already checked
        # its continuity. It emits no profile, but never hides a failed route.
        if len(cells) > 1:
            result.append(replace(segment, polyline_cells=cells))
        if cells and cells[-1] == path[-1]:
            break
    return tuple(result)


def prepare_river(world: World, heightmap: SurfaceHeightmap, request: RiverRouteRequest,
                   occupied: dict[Coord, MapCellHydrology], topology: WorldTopology,
                   policy: HydrologyRiversPolicy, bodies: Sequence[WaterBody],
                   ctx: ResolveContext, z_min: int, *, space: CoordinateSpace) -> PreparedRiver:
    if request.rejected_connection_type is not None:
        return _invalid_type(world, request, space, request.rejected_connection_type)
    # Validate every segment before any profile/claim is published. A request
    # supplied by another producer must have the same per-object error boundary.
    for segment in request.segments:
        try:
            HydrologyConnectionType(segment.connection_type)
        except ValueError:
            return _invalid_type(world, request, space, segment.connection_type)
    checked = validate_route(request, heightmap, occupied, topology, policy, bodies)
    path = checked.path
    diagnostics = ()
    if checked.failure is not None:
        fallback_reason = None
        has_receivers = bool(bodies) or any(entry.role is Role.RIVER_BED or (
            entry.role is not None and entry.role.is_open_water_role()) or (
            entry.water_body_uid is not None and entry.z_water_level is not None)
            for entry in occupied.values())
        if checked.invalid_source:
            code = Code.INVALID_SOURCE
        elif checked.failure is Failure.DRAINAGE_CYCLE:
            code = Code.TARGET_UNREACHABLE
        elif not has_receivers:
            code = Code.NO_WATER_BODIES
        elif not is_runtime_river_context(ctx):
            code = Code.TARGET_UNREACHABLE
        else:
            search = fallback_route(request, heightmap, occupied, topology, policy, bodies)
            path, fallback_reason = search.path, search.failure
            code = Code.REDIRECTED if path else (
                Code.NO_REACHABLE_WATER if has_receivers else Code.NO_WATER_BODIES)
        receiving = occupied[path[-1]] if path and code is Code.REDIRECTED else None
        diagnostics = (_diagnostic(world, request, space, code=code, reason=checked.failure,
            failure_cell=checked.failure_cell, fallback_reason=fallback_reason, receiver=receiving,
            cell=path[-1] if receiving else None, occupied=occupied, bodies=bodies),)
        if code is not Code.REDIRECTED:
            return PreparedRiver(diagnostics=diagnostics)
    receiver_cell = path[-1]
    entry = occupied[receiver_cell]
    drainage = RiverDrainageLink(river_uid=request.object_uid, river_type=request.object_type,
        receiver_uid=entry.water_body_uid,
        receiver_kind=receiver_kind(receiver_cell, occupied, bodies),
        receiver_cell=diagnostic_cell(world, receiver_cell, space))
    segments = _selected_segments(request, path, bool(diagnostics))
    specs, accepted = [], []
    # The confirmed receiver cell is excluded explicitly, also for confluences:
    # is_river_mouth deliberately does not classify every RIVER_BED as open water.
    for segment in segments:
        cells = list(segment.polyline_cells)
        bed_cells = cells[:-1] if cells and cells[-1] == receiver_cell else cells
        profile_segment = replace(segment, polyline_cells=bed_cells)
        spec = river_bed_spec(heightmap, profile_segment,
            depth_step=policy.channel_depth_for(HydrologyConnectionType(segment.connection_type)),
            z_min=z_min, occupied=occupied)
        if spec.bed_z:
            accepted.append(segment)
            specs.append(spec)
    if not specs:
        return PreparedRiver(diagnostics=(_diagnostic(world, request, space,
            code=Code.INVALID_SOURCE, reason=Failure.MISSING_GEOMETRY),))
    return PreparedRiver(tuple(accepted), tuple(specs), diagnostics, drainage)


def prepare_river_requests(world: World, heightmap: SurfaceHeightmap, requests: Sequence[RiverRouteRequest],
                           claims: dict[Coord, MapCellHydrology], topology: WorldTopology,
                           policy: HydrologyRiversPolicy, water_bodies: Sequence[WaterBody],
                           ctx: ResolveContext, z_min: int, *, space: CoordinateSpace) -> list[PreparedRiver]:
    """Prepare receivers first; claims retain rooted drainage and never mutate z."""
    jobs = []
    for request in order_river_requests(requests, heightmap.surface_z, claims):
        job = prepare_river(world, heightmap, request, claims, topology, policy, water_bodies, ctx, z_min, space=space)
        jobs.append(job)
        for segment, spec in zip(job.segments, job.specs, strict=True):
            claims.update(river_bed_roles(segment, spec, drainage=job.drainage))
    return jobs
