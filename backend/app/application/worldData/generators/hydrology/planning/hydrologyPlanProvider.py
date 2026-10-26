"""Planning dependency adapters for hydrology routes and final facts."""

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, HydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput, HydrologyPlanInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


def _failure(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("dependencies",), message),))


class HydrologyRoutesPlanProvider:
    def __init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 water_placement: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan],
                 assembler: HydrologyRoutesAssembler) -> None:
        self._relief, self._water = relief, water_placement
        self._assembler = assembler

    def build(self, request: PlanRequest[HydrologyPlanInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[HydrologyRoutesPlan]:
        control.raise_if_shutdown()
        relief = dependencies.require(PlanSlot(SurfacePlanSlot.RELIEF.value), self._relief)
        water = dependencies.require(PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value), self._water)
        self._require_refs(relief, water)
        return self._assembler.assemble(world_uid=request.key.world_uid, inputs=request.inputs,
            relief=relief.payload, placement=water.payload, control=control)

    def _require_refs(self, relief: PlanEnvelope[ReliefPlan], water: PlanEnvelope[WaterPlacementPlan]) -> None:
        refs = {dep.slot: dep.ref for dep in relief.dependencies}
        if refs.get(PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value)) != water.ref:
            raise _failure("routes must use relief's exact water-placement ref")


class HydrologyFinalPlanProvider:
    def __init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 hydrology_routes: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan],
                 river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan],
                 assembler: HydrologyFactsAssembler) -> None:
        self._relief, self._routes, self._river = relief, hydrology_routes, river_relief
        self._assembler = assembler

    def build(self, request: PlanRequest[HydrologyFinalInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[HydrologyPlan]:
        control.raise_if_shutdown()
        relief = dependencies.require(PlanSlot(SurfacePlanSlot.RELIEF.value), self._relief)
        routes = dependencies.require(PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value), self._routes)
        river = dependencies.require(PlanSlot(SurfacePlanSlot.RIVER_RELIEF.value), self._river)
        self._require_refs(relief, routes, river)
        return self._assembler.assemble(inputs=request.inputs, relief=relief.payload,
            routes=routes.payload, river=river.payload, control=control)

    def _require_refs(self, relief: PlanEnvelope[ReliefPlan], routes: PlanEnvelope[HydrologyRoutesPlan],
                      river: PlanEnvelope[RiverReliefPlan]) -> None:
        route_refs = {dep.slot: dep.ref for dep in routes.dependencies}
        river_refs = {dep.slot: dep.ref for dep in river.dependencies}
        if (route_refs.get(PlanSlot(SurfacePlanSlot.RELIEF.value)) != relief.ref
                or river_refs.get(PlanSlot(SurfacePlanSlot.RELIEF.value)) != relief.ref
                or river_refs.get(PlanSlot(SurfacePlanSlot.HYDROLOGY_ROUTES.value)) != routes.ref):
            raise _failure("final water requires exact pre-relief/routes/river-relief refs")
