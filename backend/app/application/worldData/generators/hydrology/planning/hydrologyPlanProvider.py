"""Frozen baseline routes and final water facts; terrain alone writes river beds."""

from collections.abc import Callable, Mapping
from dataclasses import replace
from itertools import chain

from app.application.jsonValidation.resolve import ResolveContext
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.coordinates.space import CoordinateSpace
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import _grid_segments
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import (
    LoadedDeclaredHydrology, load_prepared_declared_hydrology,
)
from app.application.worldData.generators.hydrology.rivers.classifyRiverSegments import classify_autoresolve_polyline
from app.application.worldData.generators.hydrology.rivers.riverBedProfile import river_bed_roles
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import plan_prepared_river_network
from app.application.worldData.generators.hydrology.rivers.riverPrepare import PreparedRiver, prepare_river_requests_from_inputs
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import (
    prepared_declared_river_requests, request_from_prepared_segments,
)
from app.application.worldData.generators.hydrology.shore.fineRiverSampling import sample_prepared_fine_river_input
from app.application.worldData.generators.hydrology.types import RiverSegment, resolve_scopes
from app.application.worldData.generators.hydrology.waterBodyAssembler import assemble_water_bodies
from app.application.worldData.generators.terrain.reliefObjects.riverBed import RiverBedSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.enums.hydrologyConnectionType import HydrologyConnectionType
from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import (
    CoastlinePaint, DeclaredWaterPaint, HydrologyPlan, HydrologyRoutesPlan,
    IntentRiverPaint, LakePaint, RiverPathSegment, RiverRoute, SegmentRiverPaint,
)
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput, HydrologyPlanInput
from app.dataModel.hydrology.riverRouting import RiverRoutingCode
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic, PlanDiagnosticDisposition
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.spatial.grid.coordinateTypes import FineDelta, FineX, FineXY, FineY, FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverBedRecord, RiverReliefPlan
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import Coord, WorldTopology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.validation.enums.resolutionMode import ResolutionMode
from app.dataModel.worldPack.wire.hydrologyMaskWire import HydrologyMaskWire


def _failure(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("dependencies",), message),))


def _coarse(cell: Coord) -> SurfaceGridCoord:
    return SurfaceGridCoord(GridX(cell[0]), GridY(cell[1]))


def _fine(cell: Coord) -> FineXY:
    return FineX(cell[0]), FineY(cell[1])


def _heightmap(world_uid: str, topology: WorldTopology, rows: tuple[tuple[SurfaceGridCoord, FineZ], ...]) -> SurfaceHeightmap:
    bounds = topology.bounds
    if (len(rows) != bounds.width * bounds.height or any(
            topology.canonicalize(cell.gx, cell.gy) != (cell.gx, cell.gy) for cell, _ in rows)):
        raise _failure("hydrology requires complete canonical pre-river relief")
    return SurfaceHeightmap(world_uid, GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max),
        {(cell.gx, cell.gy): int(z) for cell, z in rows})


def _routes[S](jobs: list[PreparedRiver], convert: Callable[[Coord], S]) -> tuple[RiverRoute[S], ...]:
    result = []
    for job in jobs:
        if not job.segments:
            continue
        if job.drainage is None:
            raise _failure("accepted route is missing drainage proof")
        result.append(RiverRoute[S](river_uid=job.drainage.river_uid,
            segments=tuple(RiverPathSegment[S](path=tuple(map(convert, segment.polyline_cells)),
                connection_type=HydrologyConnectionType(segment.connection_type), edge_uid=segment.edge_uid,
                location_uid=segment.location_uid, declared=segment.declared) for segment in job.segments),
            receiver_cell=convert(job.segments[-1].polyline_cells[-1]), drainage=job.drainage))
    return tuple(result)


def _claims(jobs: list[PreparedRiver]) -> dict[Coord, MapCellHydrology]:
    result: dict[Coord, MapCellHydrology] = {}
    for job in jobs:
        for segment, spec in zip(job.segments, job.specs, strict=True):
            result.update(river_bed_roles(segment, spec, drainage=job.drainage))
    return result


def _paint(loaded: LoadedDeclaredHydrology, anchors: Mapping[str, Coord], ctx: ResolveContext) -> DeclaredWaterPaint:
    intents = []
    width = HydrologyMaskWire(width=1).width
    if width is None:
        raise _failure("river paint width requires resolved wire clamp")
    for river in loaded.river_intents:
        path = []
        if river.source is not None:
            path.append((river.source.x, river.source.y))
        missing = False
        for uid in river.route_location_uids:
            point = anchors.get(uid)
            if point is None:
                missing = True
            else:
                path.append(point)
        if river.mouth is not None:
            mouth = river.mouth
            point = anchors.get(mouth.location_uid) if mouth.location_uid else (
                (mouth.x, mouth.y) if mouth.x is not None and mouth.y is not None else None)
            if point is None:
                missing = True
            else:
                path.append(point)
        if missing or len(path) < 2:
            ctx.errors.append(FieldPathError(("hydrology", "rivers", river.location_uid),
                "declared paint requires complete authored anchors", code="RIVER_MISSING_PAINT_GEOMETRY"))
            continue
        intents.append(IntentRiverPaint(river_uid=river.location_uid, path=tuple(map(_fine, path)),
            width_wire=width))
    segments = []
    for edge in loaded.river_edges:
        if edge.width_cells <= 0:
            ctx.errors.append(FieldPathError(("hydrology", "rivers", edge.edge_uid),
                "declared paint requires positive fine width", code="RIVER_INVALID_PAINT_WIDTH"))
            continue
        segments.append(SegmentRiverPaint(edge_uid=edge.edge_uid, location_uid=edge.location_uid,
            segment=(_fine(edge.segment[0]), _fine(edge.segment[1])), width_fine=FineDelta(edge.width_cells)))
    return DeclaredWaterPaint(
        lakes=tuple(LakePaint(location_uid=lake.location_uid,
            shoreline_segments=tuple((_fine(a), _fine(b)) for a, b in lake.shoreline_segments)) for lake in loaded.lake_specs),
        coastlines=tuple(CoastlinePaint(location_uid=coast.location_uid,
            segments=tuple((_fine(a), _fine(b)) for a, b in coast.segments)) for coast in loaded.coastline_specs),
        segments=tuple(segments), intents=tuple(intents))


class HydrologyRoutesPlanProvider:
    def __init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 water_placement: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan]) -> None:
        self._relief, self._water = relief, water_placement

    def build(self, request: PlanRequest[HydrologyPlanInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[HydrologyRoutesPlan]:
        control.raise_if_shutdown()
        relief = dependencies.require(PlanSlot(SurfacePlanSlot.RELIEF.value), self._relief)
        water = dependencies.require(PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value), self._water)
        refs = {dep.slot: dep.ref for dep in relief.dependencies}
        if refs.get(PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value)) != water.ref:
            raise _failure("routes must use relief's exact water-placement ref")
        inputs = request.inputs
        if inputs.topology != water.payload.topology:
            raise _failure("hydrology and water placement require the same topology")
        hm = _heightmap(request.key.world_uid, inputs.topology, relief.payload.surface_z)
        if any(not inputs.z_min <= z <= inputs.z_max for z in hm.surface_z.values()):
            raise _failure("pre-river relief outside captured world z bounds")
        ctx = ResolveContext(collect_only=True, validate_only=inputs.resolution_mode is ResolutionMode.VALIDATE_ONLY)
        loaded = load_prepared_declared_hydrology(list(inputs.coastlines), list(inputs.declared_lakes),
                                                list(inputs.declared_rivers), [])
        anchors = {anchor.location_uid: anchor.position for anchor in inputs.anchors if anchor.position is not None}
        paint = _paint(loaded, anchors, ctx)
        occupied: dict[Coord, MapCellHydrology] = {}
        bodies, unions = (), ()
        coarse_jobs: list[PreparedRiver] = []
        fine_jobs: list[PreparedRiver] = []
        fine_base: dict[Coord, int] = {}
        scopes = resolve_scopes(inputs.scopes)
        seas = bool(scopes & {HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN})
        lakes = HydrologyScope.LAKES in scopes
        if inputs.enabled and (seas or lakes):
            specs = tuple(spec for spec in water.payload.basin_specs if (
                lakes and inputs.lakes.enabled if spec.kind is BasinKind.LAKE else seas and inputs.seas.enabled))
            policy = WorldHydrology(default_water_level=inputs.default_water_level,
                default_seas=inputs.seas, default_lakes=inputs.lakes, default_rivers=inputs.rivers)
            assembled = assemble_water_bodies(hm, specs, inputs.topology, policy, change_uid=inputs.change_uid,
                auto_seas=bool(seas and inputs.seas.enabled and (
                    inputs.seas.autoresolve_coastal_sea or inputs.seas.autoresolve_open_ocean)),
                auto_lakes=bool(lakes and inputs.lakes.enabled and inputs.lakes.autoresolve), ctx=ctx,
                allowed_kinds=frozenset(([BasinKind.LAKE] if lakes and inputs.lakes.enabled else []) + (
                    [BasinKind.SEA, BasinKind.OCEAN, BasinKind.INLAND_SEA] if seas and inputs.seas.enabled else [])))
            occupied = assembled.materialized.by_cell
            bodies, unions = assembled.materialized.bodies, assembled.physical_unions
        control.raise_if_shutdown()
        if inputs.enabled and HydrologyScope.RIVERS in scopes:
            span, classify = inputs.grid.fine_span, inputs.rivers.type_classify
            coarse_edges = [replace(edge, segment=_grid_segments([edge.segment], span, inputs.topology)[0])
                            for edge in loaded.river_edges]
            requests = prepared_declared_river_requests(span, inputs.rivers.mouth_search_radius_fine,
                hm, coarse_edges, loaded.river_intents, anchors, occupied, classify, inputs.topology,
                space=CoordinateSpace.WORLD_SURFACE_GRID)
            claims = dict(occupied)
            coarse_jobs = prepare_river_requests_from_inputs(request.key.world_uid, span, hm, requests, claims,
                inputs.topology, inputs.rivers, bodies, ctx, inputs.z_min,
                space=CoordinateSpace.WORLD_SURFACE_GRID, build_profiles=False, check=control.raise_if_shutdown)
            if inputs.rivers.enabled and inputs.rivers.autoresolve:
                paths = plan_prepared_river_network(request.key.world_uid, inputs.seed, inputs.rivers,
                    hm, claims, classify, topology=inputs.topology)
                auto = [classify_autoresolve_polyline(path, hm, classify,
                    edge_uid=f"ar-river-{request.key.world_uid}-{path[0][0]}-{path[0][1]}-{index}")
                    for index, path in enumerate(paths)]
                requests = [request_from_prepared_segments(span, (segment,), occupied, hm.surface_z,
                            space=CoordinateSpace.WORLD_SURFACE_GRID) for segment in auto]
                coarse_jobs.extend(prepare_river_requests_from_inputs(request.key.world_uid, span, hm, requests,
                    claims, inputs.topology, inputs.rivers, bodies, ctx, inputs.z_min,
                    space=CoordinateSpace.WORLD_SURFACE_GRID, build_profiles=False, check=control.raise_if_shutdown))
            control.raise_if_shutdown()
            fine_top = fine_topology(inputs.topology, span)
            sampling = sample_prepared_fine_river_input(request.key.world_uid, span, loaded, anchors, hm.surface_z,
                fine_top, CoordinateSpace.WORLD_SURFACE_GRID, occupied | _claims(coarse_jobs), {}, inputs.rivers)
            requests = prepared_declared_river_requests(span, inputs.rivers.mouth_search_radius_fine,
                sampling.heightmap, loaded.river_edges, loaded.river_intents, anchors, sampling.occupied,
                classify, fine_top, space=CoordinateSpace.WORLD_FINE_GRID)
            requests = sampling.sample_requests(requests, classify)
            fine_jobs = prepare_river_requests_from_inputs(request.key.world_uid, span, sampling.heightmap,
                requests, dict(sampling.occupied), fine_top, inputs.rivers, bodies, ctx, inputs.z_min,
                space=CoordinateSpace.WORLD_FINE_GRID, build_profiles=False, check=control.raise_if_shutdown)
            fine_base = sampling.output_heightmap(cell for segments in chain(
                (req.segments for req in requests), (job.segments for job in fine_jobs))
                for segment in segments for cell in segment.polyline_cells).surface_z
        retained = {"WATER_KIND_MISMATCH", "WATER_LEVEL_SPILL", "WATER_LEVEL_SUPERSEDED"}
        diagnostics = [PlanDiagnostic(issue=issue, disposition=(PlanDiagnosticDisposition.FALLBACK
            if issue.code in retained else PlanDiagnosticDisposition.NOTICE if issue.code == "WATER_WORLD_OCEAN"
            else PlanDiagnosticDisposition.ERROR)) for issue in dict.fromkeys(ctx.errors)]
        for job in (*coarse_jobs, *fine_jobs):
            for fact in job.diagnostics:
                diagnostics.append(PlanDiagnostic(issue=FieldPathError(("hydrology", "rivers", fact.object_uid),
                    fact.model_dump_json(), code=fact.code.value), disposition=(PlanDiagnosticDisposition.FALLBACK
                    if fact.code is RiverRoutingCode.REDIRECTED else PlanDiagnosticDisposition.ERROR)))
        control.raise_if_shutdown()
        return PlanBuildResult[HydrologyRoutesPlan](payload=HydrologyRoutesPlan(
            coarse_open_water=tuple((_coarse(cell), occupied[cell]) for cell in sorted(occupied, key=lambda c: (c[1], c[0]))),
            water_bodies=bodies, physical_unions=unions, coarse_routes=_routes(coarse_jobs, _coarse),
            fine_routes=_routes(fine_jobs, _fine), fine_base_surface_z=tuple(
                (_fine(cell), FineZ(fine_base[cell])) for cell in sorted(fine_base, key=lambda c: (c[1], c[0]))),
            declared_paint=paint), diagnostics=tuple(dict.fromkeys(diagnostics)))


def _final_roles[S](routes: tuple[RiverRoute[S], ...], beds: tuple[RiverBedRecord[S], ...],
                    surface: tuple[tuple[S, FineZ], ...], to_xy: Callable[[S], Coord],
                    control: PlanBuildControl) -> dict[Coord, MapCellHydrology]:
    records = {bed.river_uid: dict(bed.bed_z) for bed in beds}
    if set(records) != {route.river_uid for route in routes}:
        raise _failure("actual river beds must join accepted routes by UID in each space")
    heights = dict(surface)
    result = {}
    for route in routes:
        control.raise_if_shutdown()
        record = records[route.river_uid]
        expected = {cell for segment in route.segments for cell in segment.path if cell != route.receiver_cell}
        if (set(record) != expected or route.receiver_cell not in heights
                or any(heights.get(cell) != z for cell, z in record.items())):
            raise _failure("incomplete or inconsistent actual bed/receiver mapping")
        for segment in route.segments:
            prepared = RiverSegment([to_xy(cell) for cell in segment.path], segment.connection_type.value,
                edge_uid=segment.edge_uid, location_uid=segment.location_uid, declared=segment.declared)
            spec = RiverBedSpec(tuple((to_xy(cell), record[cell]) for cell in segment.path if cell in record))
            result.update(river_bed_roles(prepared, spec, drainage=route.drainage))
    return result


def _receivers[S](routes: tuple[RiverRoute[S], ...], occupied: Mapping[Coord, MapCellHydrology],
                  to_xy: Callable[[S], Coord]) -> None:
    for route in routes:
        receiver = occupied.get(to_xy(route.receiver_cell))
        if receiver is None or receiver.water_body_uid != route.drainage.receiver_uid:
            raise _failure("accepted receiver must retain its actual receiving-water identity")


class HydrologyFinalPlanProvider:
    def __init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 hydrology_routes: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan],
                 river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan]) -> None:
        self._relief, self._routes, self._river = relief, hydrology_routes, river_relief

    def build(self, request: PlanRequest[HydrologyFinalInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[HydrologyPlan]:
        control.raise_if_shutdown()
        relief = dependencies.require(PlanSlot(SurfacePlanSlot.RELIEF.value), self._relief)
        routes = dependencies.require(PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value), self._routes)
        river = dependencies.require(PlanSlot(SurfacePlanSlot.RIVER_RELIEF.value), self._river)
        route_refs = {dep.slot: dep.ref for dep in routes.dependencies}
        river_refs = {dep.slot: dep.ref for dep in river.dependencies}
        if (route_refs.get(PlanSlot(SurfacePlanSlot.RELIEF.value)) != relief.ref
                or river_refs.get(PlanSlot(SurfacePlanSlot.RELIEF.value)) != relief.ref
                or river_refs.get(PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value)) != routes.ref):
            raise _failure("final water requires exact pre-relief/routes/river-relief refs")
        _heightmap(request.key.world_uid, request.inputs.topology, river.payload.surface_z)
        if ({cell for cell, _ in river.payload.surface_z} != {cell for cell, _ in relief.payload.surface_z}
                or {cell for cell, _ in river.payload.fine_surface_z}
                != {cell for cell, _ in routes.payload.fine_base_surface_z}):
            raise _failure("final river surface must preserve complete coarse and sampled fine coverage")
        base = routes.payload
        coarse: dict[Coord, MapCellHydrology] = {(cell.gx, cell.gy): value for cell, value in base.coarse_open_water}
        coarse.update(_final_roles(base.coarse_routes, river.payload.coarse_beds, river.payload.surface_z,
                                  lambda cell: (cell.gx, cell.gy), control))
        fine = _final_roles(base.fine_routes, river.payload.fine_beds, river.payload.fine_surface_z,
                            lambda cell: cell, control)
        _receivers(base.coarse_routes, coarse, lambda cell: (cell.gx, cell.gy))
        fine_top = fine_topology(request.inputs.topology, request.inputs.grid.fine_span)
        if any(fine_top.canonicalize(*cell) != cell for cell, _ in river.payload.fine_surface_z):
            raise _failure("fine river samples outside final topology")
        span = request.inputs.grid.fine_span
        receivers = {route.receiver_cell: coarse[(route.receiver_cell[0] // span, route.receiver_cell[1] // span)]
            for route in base.fine_routes
            if (route.receiver_cell[0] // span, route.receiver_cell[1] // span) in coarse}
        _receivers(base.fine_routes, receivers | fine, lambda cell: cell)
        if not request.inputs.enabled and (coarse or fine or base.water_bodies or base.physical_unions):
            raise _failure("disabled hydrology cannot consume active water facts")
        control.raise_if_shutdown()
        return PlanBuildResult[HydrologyPlan](payload=HydrologyPlan(
            coarse_surface_z=river.payload.surface_z, fine_z_overrides=river.payload.fine_surface_z,
            coarse_hydro=tuple((_coarse(cell), coarse[cell]) for cell in sorted(coarse, key=lambda c: (c[1], c[0]))),
            sparse_fine_hydro=tuple((_fine(cell), fine[cell]) for cell in sorted(fine, key=lambda c: (c[1], c[0]))),
            water_bodies=base.water_bodies, physical_unions=base.physical_unions, declared_paint=base.declared_paint), diagnostics=())
