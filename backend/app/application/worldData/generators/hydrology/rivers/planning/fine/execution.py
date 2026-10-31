"""Own sparse fine sampling, route planning and retained pre-river sample delivery."""

from itertools import chain
from collections.abc import Mapping

from app.dataModel.hydrology.waterBody import WaterBody
from app.dataModel.topology.worldTopology import WorldTopology

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import load_prepared_declared_hydrology
from app.application.worldData.generators.hydrology.rivers.riverPrepare import plan_prepared_routes
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import prepared_declared_river_requests
from app.application.worldData.generators.hydrology.shore.fineRiverSampling import sample_prepared_fine_river_input
from app.application.worldData.generators.hydrology.types import resolve_scopes
from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan, FineWaterResult
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineXY, FineY, FineZ, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _fine(cell: Coord) -> FineXY:
    return FineX(cell[0]), FineY(cell[1])


class FineRiverJob:
    def plan(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput | GeoHydrologyPlanInput,
             surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], water: OpenWaterPlan,
             coarse: CoarseRiverPlan, control: PlanBuildControl) -> PlanBuildResult[FineRiverPlan]:
        control.raise_if_shutdown()
        if not inputs.enabled or HydrologyScope.RIVERS not in resolve_scopes(inputs.scopes):
            return PlanBuildResult[FineRiverPlan](payload=FineRiverPlan(routes=(), base_surface_z=()), diagnostics=())
        bounds = inputs.topology.bounds
        box = GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max)
        try:
            TerrainPlan(bbox=box, surface_z=surface_z)
            if any(not inputs.z_min <= z <= inputs.z_max for _, z in surface_z):
                raise ValueError("pre-river heights outside world z bounds")
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("surface_z",), str(error)),)) from error
        base: dict[Coord, int] = {(cell.gx, cell.gy): int(z) for cell, z in surface_z}
        if any((cell.gx, cell.gy) not in base for cell, _ in coarse.claims):
            raise PlanBuildFailure((FieldPathError(("coarse",), "coarse river claims outside pre-river surface"),))
        occupied: dict[Coord, MapCellHydrology] = {(cell.gx, cell.gy): value for cell, value in water.coarse_open_water}
        occupied.update({(cell.gx, cell.gy): value for cell, value in coarse.claims})
        return self._route(world_uid=world_uid, inputs=inputs, base=base,
            coarse_hydro=occupied, fine_hydro={}, space=CoordinateSpace.WORLD_SURFACE_GRID,
            topology=fine_topology(inputs.topology, inputs.grid.fine_span),
            water_bodies=water.water_bodies, control=control)

    def plan_fine(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                  water: FineWaterResult, control: PlanBuildControl) -> PlanBuildResult[FineRiverPlan]:
        control.raise_if_shutdown()
        if not inputs.enabled or HydrologyScope.RIVERS not in resolve_scopes(inputs.scopes):
            return PlanBuildResult[FineRiverPlan](payload=FineRiverPlan(routes=(), base_surface_z=()), diagnostics=())
        window, assembled = water
        return self._route(world_uid=world_uid, inputs=inputs,
            base=dict(window.surface_z), coarse_hydro={}, fine_hydro=dict(assembled.materialized.cells),
            space=CoordinateSpace.WORLD_FINE_GRID, topology=window.topology,
            water_bodies=assembled.materialized.bodies, control=control)

    def _route(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput | GeoHydrologyPlanInput,
               base: Mapping[Coord, int], coarse_hydro: Mapping[Coord, MapCellHydrology],
               fine_hydro: Mapping[Coord, MapCellHydrology], space: CoordinateSpace,
               topology: WorldTopology, water_bodies: tuple[WaterBody, ...],
               control: PlanBuildControl) -> PlanBuildResult[FineRiverPlan]:
        loaded = load_prepared_declared_hydrology([], [], list(inputs.declared_rivers), [])
        anchors = {anchor.location_uid: anchor.position for anchor in inputs.anchors if anchor.position is not None}
        span, classify = inputs.grid.fine_span, inputs.rivers.type_classify
        sampling = sample_prepared_fine_river_input(world_uid, span, loaded, anchors, base,
            topology, space, coarse_hydro, fine_hydro, inputs.rivers)
        control.raise_if_shutdown()
        requests = prepared_declared_river_requests(span, inputs.rivers.mouth_search_radius_fine,
            sampling.heightmap, loaded.river_edges, loaded.river_intents, anchors, sampling.occupied,
            classify, topology, space=CoordinateSpace.WORLD_FINE_GRID)
        requests = sampling.sample_requests(requests, classify)
        result = plan_prepared_routes(world_uid=world_uid, span=span, heightmap=sampling.heightmap,
            requests=requests, claims=sampling.occupied, topology=topology, policy=inputs.rivers,
            water_bodies=water_bodies, resolution_mode=inputs.resolution_mode, z_min=inputs.z_min,
            space=CoordinateSpace.WORLD_FINE_GRID, to_coordinate=_fine, control=control)
        retained = chain((cell for request in requests for segment in request.segments for cell in segment.polyline_cells),
                         (cell for route in result.payload.routes for segment in route.segments for cell in segment.path),
                         (route.receiver_cell for route in result.payload.routes))
        samples = sampling.output_heightmap(retained).surface_z
        control.raise_if_shutdown()
        return PlanBuildResult[FineRiverPlan](payload=FineRiverPlan(routes=result.payload.routes,
            base_surface_z=tuple((_fine(cell), FineZ(samples[cell])) for cell in sorted(samples, key=lambda cell: (cell[1], cell[0])))),
            diagnostics=result.diagnostics)
