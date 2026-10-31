"""Public native river-relief operation; delegate proof binding and bed execution."""
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.relief.planning.river.publication import NativeRiverReliefPublicationJob
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import FineWaterResult
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan


class RiverReliefPlanner:
    def plan_fine(self, inputs: RiverReliefInput, *, world_uid: EntityUid,
                  routing_inputs: GeoHydrologyPlanInput, water: PlanEnvelope[FineWaterResult],
                  expected_water: PlanRef, routes: PlanEnvelope[GeoHydrologyRoutesPlan],
                  expected_routes: PlanRef, control: PlanBuildControl) -> PlanEnvelope[RiverReliefPlan]:
        return NativeRiverReliefPublicationJob().publish(inputs, world_uid=world_uid,
            routing_inputs=routing_inputs, water=water, expected_water=expected_water,
            routes=routes, expected_routes=expected_routes, control=control)
