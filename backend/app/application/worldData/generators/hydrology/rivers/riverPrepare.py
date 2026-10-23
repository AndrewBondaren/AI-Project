"""Prepare rooted drainage atomically; relief remains the sole elevation writer."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TypeVar

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_roles, river_bed_spec
from app.application.worldData.generators.hydrology.rivers.riverMouth import is_river_mouth
from app.application.worldData.generators.hydrology.rivers.riverReceivers import receiver_kind
from app.application.worldData.generators.hydrology.rivers.riverRequestOrder import order_river_requests
from app.application.worldData.generators.hydrology.rivers.riverRouteDiagnostics import is_runtime_river_context
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest, diagnostic_cell_for_span
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
from app.dataModel.hydrology.planning.hydrologyPlan import RiverPathSegment, RiverRoute
from app.dataModel.hydrology.planning.stages.riverRoutePlans import RiverRouteBatch
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ, SurfaceGridCoord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.db.models.world import World
from app.application.worldData.generators.coordinates.convert import map_cell_fine_span


@dataclass(frozen=True)
class PreparedRiver:
    segments: tuple[RiverSegment, ...] = ()
    specs: tuple[RiverBedSpec, ...] = ()
    diagnostics: tuple[RiverRouteDiagnostic, ...] = ()
    drainage: RiverDrainageLink | None = None


def _diagnostic(world_uid: str, span: int, request: RiverRouteRequest, space: CoordinateSpace, *,
                code: Code, reason: Failure, failure_cell: Coord | None = None,
                fallback_reason: Failure | None = None, receiver: MapCellHydrology | None = None,
                cell: Coord | None = None, bodies: Sequence[WaterBody] = (),
                occupied: Mapping[Coord, MapCellHydrology] | None = None) -> RiverRouteDiagnostic:
    if receiver is not None and (cell is None or occupied is None):
        raise PlanBuildFailure((FieldPathError(("receiver",), "receiver diagnostic requires its cell and occupancy"),))
    return RiverRouteDiagnostic(
        world_uid=world_uid, object_uid=request.object_uid, object_type=request.object_type,
        rejected_connection_type=request.rejected_connection_type,
        requested_mouth=request.requested_mouth, requested_receiver_uid=request.requested_receiver_uid,
        code=code, reason=reason, fallback_reason=fallback_reason,
        source_cell=diagnostic_cell_for_span(span, request.source, space),
        failure_cell=diagnostic_cell_for_span(span, failure_cell, space),
        receiver_uid=receiver.water_body_uid if receiver else None,
        receiver_kind=receiver_kind(cell, occupied, bodies) if receiver is not None and cell is not None and occupied is not None else None,
        receiver_cell=diagnostic_cell_for_span(span, cell, space) if receiver else None,
        receiver_level=receiver.z_water_level if receiver else None,
    )


def _invalid_type(world_uid: str, span: int, request: RiverRouteRequest, space: CoordinateSpace,
                   rejected: str, emit: Callable[[PlanDiagnostic], None] | None) -> PreparedRiver:
    request = replace(request, object_type=None, rejected_connection_type=rejected)
    fact = _diagnostic(world_uid, span, request, space,
        code=Code.INVALID_CONNECTION_TYPE, reason=Failure.INVALID_CONNECTION_TYPE)
    _emit_diagnostic(fact, PlanDiagnosticDisposition.ERROR, emit)
    return PreparedRiver(diagnostics=(fact,))


def _selected_segments(request: RiverRouteRequest, path: tuple[Coord, ...], redirected: bool, kind: HydrologyConnectionType) -> tuple[RiverSegment, ...]:
    if redirected:
        template = request.segments[0] if request.segments else RiverSegment(
            [], kind.value, location_uid=request.object_uid)
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


def prepare_river_from_inputs(world_uid: str, span: int, heightmap: SurfaceHeightmap, request: RiverRouteRequest,
                   occupied: dict[Coord, MapCellHydrology], topology: WorldTopology,
                   policy: HydrologyRiversPolicy, bodies: Sequence[WaterBody],
                   ctx: ResolveContext, z_min: int, *, space: CoordinateSpace, build_profiles: bool,
                   emit: Callable[[PlanDiagnostic], None] | None = None) -> PreparedRiver:
    if request.rejected_connection_type is not None:
        return _invalid_type(world_uid, span, request, space, request.rejected_connection_type, emit)
    request_kind = request.object_type
    if request_kind is None:
        raise PlanBuildFailure((FieldPathError(("request", request.object_uid), "river request requires a valid object type"),))
    # Validate every segment before any profile/claim is published. A request
    # supplied by another producer must have the same per-object error boundary.
    for segment in request.segments:
        try:
            kind = HydrologyConnectionType(segment.connection_type)
            if kind not in (HydrologyConnectionType.RIVER, HydrologyConnectionType.MOUNTAIN_RIVER):
                return _invalid_type(world_uid, span, request, space, segment.connection_type, emit)
        except ValueError:
            return _invalid_type(world_uid, span, request, space, segment.connection_type, emit)
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
        diagnostics = (_diagnostic(world_uid, span, request, space, code=code, reason=checked.failure,
            failure_cell=checked.failure_cell, fallback_reason=fallback_reason, receiver=receiving,
            cell=path[-1] if receiving else None, occupied=occupied, bodies=bodies),)
        if code is not Code.REDIRECTED:
            _emit_diagnostic(diagnostics[0], PlanDiagnosticDisposition.ERROR, emit)
            return PreparedRiver(diagnostics=diagnostics)
    receiver_cell = path[-1]
    entry = occupied[receiver_cell]
    receiver_uid = entry.water_body_uid
    kind = receiver_kind(receiver_cell, occupied, bodies)
    diagnostic_receiver = diagnostic_cell_for_span(span, receiver_cell, space)
    if receiver_uid is None or kind is None or diagnostic_receiver is None:
        raise PlanBuildFailure((FieldPathError(("receiver", request.object_uid), "accepted receiver requires identity, kind and diagnostic cell"),))
    drainage = RiverDrainageLink(river_uid=request.object_uid, river_type=request_kind,
        receiver_uid=receiver_uid, receiver_kind=kind, receiver_cell=diagnostic_receiver)
    segments = _selected_segments(request, path, bool(diagnostics), request_kind)
    specs, accepted = [], []
    # The confirmed receiver cell is excluded explicitly, also for confluences:
    # is_river_mouth deliberately does not classify every RIVER_BED as open water.
    for segment in segments:
        cells = list(segment.polyline_cells)
        bed_cells = cells[:-1] if cells and cells[-1] == receiver_cell else cells
        profile_segment = replace(segment, polyline_cells=bed_cells)
        if build_profiles:
            spec = river_bed_spec(heightmap, profile_segment,
                depth_step=policy.channel_depth_for(HydrologyConnectionType(segment.connection_type)),
                z_min=z_min, occupied=occupied)
        else:
            # Feasibility/occupancy only. No profile or elevation decision in route planning.
            land = []
            for cell in bed_cells:
                if cell not in heightmap.surface_z:
                    continue
                if is_river_mouth(cell, heightmap.surface_z, occupied):
                    break
                land.append((cell, heightmap.surface_z[cell]))
            spec = RiverBedSpec(tuple(land))
        if spec.bed_z:
            accepted.append(segment)
            specs.append(spec)
    if not specs:
        fact = _diagnostic(world_uid, span, request, space, code=Code.INVALID_SOURCE, reason=Failure.MISSING_GEOMETRY)
        _emit_diagnostic(fact, PlanDiagnosticDisposition.ERROR, emit)
        return PreparedRiver(diagnostics=(fact,))
    # A redirect is a fallback only after it has produced an accepted land route.
    for fact in diagnostics:
        _emit_diagnostic(fact, PlanDiagnosticDisposition.FALLBACK, emit)
    return PreparedRiver(tuple(accepted), tuple(specs), diagnostics, drainage)


def prepare_river_requests_from_inputs(world_uid: str, span: int, heightmap: SurfaceHeightmap, requests: Sequence[RiverRouteRequest],
                           claims: dict[Coord, MapCellHydrology], topology: WorldTopology,
                           policy: HydrologyRiversPolicy, water_bodies: Sequence[WaterBody],
                           ctx: ResolveContext, z_min: int, *, space: CoordinateSpace, build_profiles: bool,
                           check: Callable[[], None] | None = None,
                           emit: Callable[[PlanDiagnostic], None] | None = None) -> list[PreparedRiver]:
    """Prepare receivers first; claims retain rooted drainage and never mutate z."""
    jobs = []
    for request in order_river_requests(requests, heightmap.surface_z, claims):
        if check is not None:
            check()
        job = prepare_river_from_inputs(world_uid, span, heightmap, request, claims, topology, policy, water_bodies, ctx, z_min,
                                        space=space, build_profiles=build_profiles, emit=emit)
        jobs.append(job)
        for segment, spec in zip(job.segments, job.specs, strict=True):
            claims.update(river_bed_roles(segment, spec, drainage=job.drainage))
    return jobs


def prepare_river(world: World, heightmap: SurfaceHeightmap, request: RiverRouteRequest,
    occupied: dict[Coord, MapCellHydrology], topology: WorldTopology,
    policy: HydrologyRiversPolicy, bodies: Sequence[WaterBody], ctx: ResolveContext,
    z_min: int, *, space: CoordinateSpace,
) -> PreparedRiver:
    return prepare_river_from_inputs(world.world_uid, (map_cell_fine_span(world) if space is CoordinateSpace.WORLD_SURFACE_GRID else 1), heightmap,
        request, occupied, topology, policy, bodies, ctx, z_min, space=space, build_profiles=True)


def prepare_river_requests(world: World, heightmap: SurfaceHeightmap, requests: Sequence[RiverRouteRequest],
    claims: dict[Coord, MapCellHydrology], topology: WorldTopology, policy: HydrologyRiversPolicy,
    water_bodies: Sequence[WaterBody], ctx: ResolveContext, z_min: int, *, space: CoordinateSpace,
) -> list[PreparedRiver]:
    return prepare_river_requests_from_inputs(world.world_uid, (map_cell_fine_span(world) if space is CoordinateSpace.WORLD_SURFACE_GRID else 1), heightmap,
        requests, claims, topology, policy, water_bodies, ctx, z_min, space=space, build_profiles=True)


S = TypeVar("S", SurfaceGridCoord, FineXY)


def _emit_diagnostic(fact: RiverRouteDiagnostic, disposition: PlanDiagnosticDisposition,
                     emit: Callable[[PlanDiagnostic], None] | None) -> None:
    if emit is not None:
        emit(PlanDiagnostic(issue=FieldPathError(("hydrology", "rivers", fact.object_uid),
            fact.model_dump_json(), code=fact.code.value), disposition=disposition))


def plan_prepared_routes(*, world_uid: EntityUid, span: int, heightmap: SurfaceHeightmap,
    requests: Sequence[RiverRouteRequest], claims: dict[Coord, MapCellHydrology], topology: WorldTopology,
    policy: HydrologyRiversPolicy, water_bodies: Sequence[WaterBody], resolution_mode: ResolutionMode,
    z_min: FineZ, space: CoordinateSpace, to_coordinate: Callable[[Coord], S],
    control: PlanBuildControl,
) -> PlanBuildResult[RiverRouteBatch[S]]:
    """Route-only boundary; jobs, feasibility buffers and profile switches stay private."""
    control.raise_if_shutdown()
    if space not in (CoordinateSpace.WORLD_SURFACE_GRID, CoordinateSpace.WORLD_FINE_GRID):
        raise PlanBuildFailure((FieldPathError(("space",), "unsupported river coordinate space"),))
    ctx = ResolveContext(collect_only=True, validate_only=resolution_mode is ResolutionMode.VALIDATE_ONLY)
    diagnostics: list[PlanDiagnostic] = []
    jobs = prepare_river_requests_from_inputs(world_uid, span, heightmap, requests, dict(claims), topology,
        policy, water_bodies, ctx, z_min, space=space, build_profiles=False,
        check=control.raise_if_shutdown, emit=diagnostics.append)
    routes: list[RiverRoute[S]] = []
    published: dict[Coord, MapCellHydrology] = {}
    for job in jobs:
        control.raise_if_shutdown()
        if not job.segments:
            continue
        if job.drainage is None:
            raise PlanBuildFailure((FieldPathError(("routes",), "accepted route requires drainage proof"),))
        routes.append(RiverRoute[S](river_uid=job.drainage.river_uid,
            segments=tuple(RiverPathSegment[S](path=tuple(to_coordinate(cell) for cell in segment.polyline_cells),
                connection_type=HydrologyConnectionType(segment.connection_type), edge_uid=segment.edge_uid,
                location_uid=segment.location_uid, declared=segment.declared) for segment in job.segments),
            receiver_cell=to_coordinate(job.segments[-1].polyline_cells[-1]), drainage=job.drainage))
        for segment, spec in zip(job.segments, job.specs, strict=True):
            published.update(river_bed_roles(segment, spec, drainage=job.drainage))
    coordinates = (cell for route in routes for segment in route.segments for cell in segment.path)
    if any(isinstance(cell, SurfaceGridCoord) != (space is CoordinateSpace.WORLD_SURFACE_GRID) for cell in coordinates):
        raise PlanBuildFailure((FieldPathError(("space",), "river coordinate conversion disagrees with working space"),))
    payload = RiverRouteBatch[S](routes=tuple(routes), claims=tuple(
        (to_coordinate(cell), published[cell]) for cell in sorted(published, key=lambda cell: (cell[1], cell[0]))))
    control.raise_if_shutdown()
    return PlanBuildResult[RiverRouteBatch[S]](payload=payload, diagnostics=tuple(dict.fromkeys(diagnostics)))
