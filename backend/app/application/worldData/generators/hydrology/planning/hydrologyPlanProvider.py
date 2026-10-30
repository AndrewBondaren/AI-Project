"""Planning dependency adapters for hydrology routes and final facts."""

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.policy.policyResolver import PolicyResolver
from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import resolve_hydrology_category_policies
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, HydrologyRoutesPlan, GeoHydrologyPlan, GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput, HydrologyPlanInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan, GeoWaterPlacementPlan
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


class GeoHydrologyRoutesPlanProvider:
    """Bind exact GEO dependencies and delegate policy and route production."""

    def __init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 water_placement: RegisteredPlanContract[GeoWaterPlacementInput, GeoWaterPlacementPlan],
                 assembler: HydrologyRoutesAssembler, policy: PolicyResolver) -> None:
        self._relief, self._water, self._assembler, self._policy = relief, water_placement, assembler, policy

    def build(self, request: PlanRequest[GeoHydrologyPlanInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[GeoHydrologyRoutesPlan]:
        control.raise_if_shutdown()
        relief = dependencies.require(PlanSlot(SurfacePlanSlot.RELIEF.value), self._relief)
        water = dependencies.require(PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value), self._water)
        self._require_refs(relief, water)
        inputs = request.inputs
        decisions = resolve_hydrology_category_policies(categories=inputs, enabled=inputs.enabled,
            generation=inputs.generation, defaults=inputs.defaults, mode=inputs.resolution_mode,
            resolver=self._policy, control=control)
        return self._assembler.assemble_geo(world_uid=request.key.world_uid, inputs=inputs,
            relief=relief.payload, placement=water.payload, classification_decisions=decisions, control=control)

    def _require_refs(self, relief: PlanEnvelope[ReliefPlan], water: PlanEnvelope[GeoWaterPlacementPlan]) -> None:
        refs = {dep.slot: dep.ref for dep in relief.dependencies}
        if refs.get(PlanSlot(SurfacePlanSlot.WATER_PLACEMENT.value)) != water.ref:
            raise _failure("GEO routes must use relief's exact water-placement ref")


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


class GeoHydrologyFinalPlanProvider:
    """Keep accepted-water provenance while delegating final facts to hydrology."""

    def __init__(self, relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
                 hydrology_routes: RegisteredPlanContract[GeoHydrologyPlanInput, GeoHydrologyRoutesPlan],
                 river_relief: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan],
                 water_placement: RegisteredPlanContract[GeoWaterPlacementInput, GeoWaterPlacementPlan],
                 assembler: HydrologyFactsAssembler) -> None:
        self._relief, self._routes, self._river, self._water = relief, hydrology_routes, river_relief, water_placement
        self._assembler = assembler

    def build(self, request: PlanRequest[HydrologyFinalInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[GeoHydrologyPlan]:
        control.raise_if_shutdown()
        S = SurfacePlanSlot
        relief = dependencies.require(PlanSlot(S.RELIEF.value), self._relief)
        routes = dependencies.require(PlanSlot(S.HYDROLOGY_ROUTES.value), self._routes)
        river = dependencies.require(PlanSlot(S.RIVER_RELIEF.value), self._river)
        water = dependencies.require(PlanSlot(S.WATER_PLACEMENT.value), self._water)
        self._require_refs(relief, routes, river, water)
        result = self._assembler.assemble(inputs=request.inputs, relief=relief.payload,
            routes=routes.payload.base, river=river.payload, control=control)
        common = result.payload
        return PlanBuildResult[GeoHydrologyPlan](payload=GeoHydrologyPlan(
            coarse_surface_z=common.coarse_surface_z, coarse_hydro=common.coarse_hydro,
            sparse_fine_hydro=common.sparse_fine_hydro, fine_z_overrides=common.fine_z_overrides,
            water_bodies=common.water_bodies, physical_unions=common.physical_unions,
            declared_paint=common.declared_paint, source_mapping=routes.payload.source_mapping,
            classification_decisions=routes.payload.classification_decisions), diagnostics=result.diagnostics)

    def _require_refs(self, relief: PlanEnvelope[ReliefPlan], routes: PlanEnvelope[GeoHydrologyRoutesPlan],
                      river: PlanEnvelope[RiverReliefPlan], water: PlanEnvelope[GeoWaterPlacementPlan]) -> None:
        S = SurfacePlanSlot
        route_refs = {dep.slot: dep.ref for dep in routes.dependencies}
        river_refs = {dep.slot: dep.ref for dep in river.dependencies}
        relief_refs = {dep.slot: dep.ref for dep in relief.dependencies}
        if (route_refs.get(PlanSlot(S.RELIEF.value)) != relief.ref
                or river_refs.get(PlanSlot(S.RELIEF.value)) != relief.ref
                or river_refs.get(PlanSlot(S.HYDROLOGY_ROUTES.value)) != routes.ref
                or route_refs.get(PlanSlot(S.WATER_PLACEMENT.value)) != water.ref
                or relief_refs.get(PlanSlot(S.WATER_PLACEMENT.value)) != water.ref):
            raise _failure("GEO final water requires exact relief/routes/river-relief/water-placement refs")
