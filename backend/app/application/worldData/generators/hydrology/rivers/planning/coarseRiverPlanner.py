"""Own declared-before-procedural coarse route planning, without bed materialization."""

from dataclasses import replace

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import prepare_procedural_river_requests
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import _grid_segments
from app.application.worldData.generators.hydrology.load.loadDeclaredHydrology import load_prepared_declared_hydrology
from app.application.worldData.generators.hydrology.rivers.riverPrepare import plan_prepared_routes
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import prepared_declared_river_requests
from app.application.worldData.generators.hydrology.types import resolve_scopes
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.planning.hydrologyScope import HydrologyScope
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.spatial.grid.gridBBox import GridBBox
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _coarse(cell: Coord) -> SurfaceGridCoord:
    return SurfaceGridCoord(GridX(cell[0]), GridY(cell[1]))


class CoarseRiverPlanner:
    def plan(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput | GeoHydrologyPlanInput,
             surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], water: OpenWaterPlan,
             control: PlanBuildControl) -> PlanBuildResult[CoarseRiverPlan]:
        control.raise_if_shutdown()
        if not inputs.enabled or HydrologyScope.RIVERS not in resolve_scopes(inputs.scopes):
            return PlanBuildResult[CoarseRiverPlan](payload=CoarseRiverPlan(routes=(), claims=()), diagnostics=())
        bounds = inputs.topology.bounds
        box = GridBBox(bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max)
        try:
            TerrainPlan(bbox=box, surface_z=surface_z)
            if any(not inputs.z_min <= z <= inputs.z_max for _, z in surface_z):
                raise ValueError("pre-river heights outside world z bounds")
        except ValueError as error:
            raise PlanBuildFailure((FieldPathError(("surface_z",), str(error)),)) from error
        hm = SurfaceHeightmap(world_uid, box, {(cell.gx, cell.gy): int(z) for cell, z in surface_z})
        loaded = load_prepared_declared_hydrology([], [], list(inputs.declared_rivers), [])
        anchors = {anchor.location_uid: anchor.position for anchor in inputs.anchors if anchor.position is not None}
        span, classify = inputs.grid.fine_span, inputs.rivers.type_classify
        edges = [replace(edge, segment=_grid_segments([edge.segment], span, inputs.topology)[0])
                 for edge in loaded.river_edges]
        occupied: dict[Coord, MapCellHydrology] = {(cell.gx, cell.gy): value for cell, value in water.coarse_open_water}
        requests = prepared_declared_river_requests(span, inputs.rivers.mouth_search_radius_fine,
            hm, edges, loaded.river_intents, anchors, occupied, classify, inputs.topology,
            space=CoordinateSpace.WORLD_SURFACE_GRID)
        declared = plan_prepared_routes(world_uid=world_uid, span=span, heightmap=hm, requests=requests,
            claims=occupied, topology=inputs.topology, policy=inputs.rivers, water_bodies=water.water_bodies,
            resolution_mode=inputs.resolution_mode, z_min=inputs.z_min, space=CoordinateSpace.WORLD_SURFACE_GRID,
            to_coordinate=_coarse, control=control)
        if not inputs.rivers.enabled or not inputs.rivers.autoresolve:
            return PlanBuildResult[CoarseRiverPlan].model_validate(declared)
        control.raise_if_shutdown()
        claims: dict[Coord, MapCellHydrology] = occupied | {(cell.gx, cell.gy): value for cell, value in declared.payload.claims}
        requests = prepare_procedural_river_requests(world_uid, inputs.seed, inputs.rivers, hm, claims, inputs.topology, span)
        auto = plan_prepared_routes(world_uid=world_uid, span=span, heightmap=hm, requests=requests,
            claims=claims, topology=inputs.topology, policy=inputs.rivers, water_bodies=water.water_bodies,
            resolution_mode=inputs.resolution_mode, z_min=inputs.z_min, space=CoordinateSpace.WORLD_SURFACE_GRID,
            to_coordinate=_coarse, control=control)
        merged = dict(declared.payload.claims) | dict(auto.payload.claims)
        payload = CoarseRiverPlan(routes=declared.payload.routes + auto.payload.routes,
            claims=tuple((cell, merged[cell]) for cell in sorted(merged, key=lambda cell: (cell.gy, cell.gx))))
        return PlanBuildResult[CoarseRiverPlan](payload=payload,
            diagnostics=tuple(dict.fromkeys(declared.diagnostics + auto.diagnostics)))
