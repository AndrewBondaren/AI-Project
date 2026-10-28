"""Positive surface hydrology contracts; checked statically by Pyright."""

from typing import assert_type

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.load.paint.declaredWaterPaintProjector import (
    DeclaredWaterPaintProjector,
)
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import (
    HydrologyFactsAssembler,
)
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import (
    HydrologyRoutesAssembler,
)
from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import (
    HydrologyFinalPlanProvider,
    HydrologyRoutesPlanProvider,
)
from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.application.worldData.generators.hydrology.rivers.riverPrepare import plan_prepared_routes
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest
from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.hydrology.planning.hydrologyPlan import (
    DeclaredWaterPaint,
    HydrologyPlan,
    HydrologyRoutesPlan,
    RiverRoute,
)
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput, HydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan, RiverRouteBatch
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import FineXY, FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from app.dataModel.topology.worldTopology import Coord


def hydrology_domain(request: PlanRequest[HydrologyPlanInput],
                     entry: CacheEntry[PlanEnvelope[HydrologyPlan]],
                     route: RiverRoute[SurfaceGridCoord]) -> HydrologyPlan:
    assert_type(request.inputs, HydrologyPlanInput)
    assert_type(route.receiver_cell, SurfaceGridCoord)
    assert_type(entry.value.payload, HydrologyPlan)
    return entry.value.payload


def hydrology_providers(routes: HydrologyRoutesPlanProvider, final: HydrologyFinalPlanProvider,
    route_request: PlanRequest[HydrologyPlanInput], final_request: PlanRequest[HydrologyFinalInput],
    reader: PlanDependencyReader, control: PlanBuildControl) -> None:
    assert_type(routes.build(route_request, reader, control), PlanBuildResult[HydrologyRoutesPlan])
    assert_type(final.build(final_request, reader, control), PlanBuildResult[HydrologyPlan])


def intermediate_hydrology_plans(water: PlanBuildResult[OpenWaterPlan], coarse: CoarseRiverPlan,
    fine_batch: RiverRouteBatch[FineXY], fine: FineRiverPlan) -> None:
    assert_type(water.payload, OpenWaterPlan)
    assert_type(coarse, RiverRouteBatch[SurfaceGridCoord])
    assert_type(coarse.routes[0].receiver_cell, SurfaceGridCoord)
    assert_type(coarse.claims[0][0], SurfaceGridCoord)
    assert_type(fine_batch.routes[0].receiver_cell, FineXY)
    assert_type(fine_batch.claims[0][0], FineXY)
    assert_type(fine.base_surface_z[0][0], FineXY)


def hydrology_water_and_paint_owners(water: WaterBodyPlanner, paint: DeclaredWaterPaintProjector,
    inputs: HydrologyPlanInput, surface: tuple[tuple[SurfaceGridCoord, FineZ], ...],
    placement: WaterPlacementPlan, control: PlanBuildControl) -> None:
    assert_type(water.plan(world_uid="world", inputs=inputs, surface_z=surface,
        placement=placement, control=control), PlanBuildResult[OpenWaterPlan])
    assert_type(paint.project(rivers=inputs.declared_rivers, coastlines=inputs.coastlines,
        lakes=inputs.declared_lakes, anchors=inputs.anchors), PlanBuildResult[DeclaredWaterPaint])


def river_owners(coarse: CoarseRiverPlanner, fine: FineRiverPlanner, inputs: HydrologyPlanInput,
    surface: tuple[tuple[SurfaceGridCoord, FineZ], ...], water: OpenWaterPlan, control: PlanBuildControl) -> None:
    first = coarse.plan(world_uid="world", inputs=inputs, surface_z=surface, water=water, control=control)
    assert_type(first, PlanBuildResult[CoarseRiverPlan])
    assert_type(fine.plan(world_uid="world", inputs=inputs, surface_z=surface, water=water,
        coarse=first.payload, control=control), PlanBuildResult[FineRiverPlan])


def route_only_coarse_contract(inputs: HydrologyPlanInput, hm: SurfaceHeightmap,
    requests: tuple[RiverRouteRequest, ...], claims: dict[Coord, MapCellHydrology],
    control: PlanBuildControl) -> None:
    result = plan_prepared_routes(world_uid="world", span=inputs.grid.fine_span, heightmap=hm,
        requests=requests, claims=claims, topology=inputs.topology, policy=inputs.rivers,
        water_bodies=(), resolution_mode=inputs.resolution_mode, z_min=inputs.z_min,
        space=CoordinateSpace.WORLD_SURFACE_GRID,
        to_coordinate=lambda c: SurfaceGridCoord(GridX(c[0]), GridY(c[1])), control=control)
    assert_type(result, PlanBuildResult[RiverRouteBatch[SurfaceGridCoord]])


def hydrology_assembly_contracts(routes_owner: HydrologyRoutesAssembler, facts_owner: HydrologyFactsAssembler,
    inputs: HydrologyPlanInput, final_inputs: HydrologyFinalInput, relief: ReliefPlan,
    placement: WaterPlacementPlan, river: RiverReliefPlan, control: PlanBuildControl,
    relief_handle: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
    water_handle: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan],
    routes_handle: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan],
    river_handle: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan]) -> PlanBuildResult[HydrologyPlan]:
    HydrologyRoutesPlanProvider(relief_handle, water_handle, routes_owner)
    HydrologyFinalPlanProvider(relief_handle, routes_handle, river_handle, facts_owner)
    routes: PlanBuildResult[HydrologyRoutesPlan] = routes_owner.assemble(world_uid="world", inputs=inputs,
        relief=relief, placement=placement, control=control)
    return facts_owner.assemble(inputs=final_inputs, relief=relief, routes=routes.payload, river=river, control=control)
