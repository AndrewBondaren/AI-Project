"""Public fine river operations; domain execution and publication belong to jobs."""
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.rivers.planning.fine.execution import FineRiverJob
from app.application.worldData.generators.hydrology.rivers.planning.fine.publication import FineRiverPublicationJob
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan, FineWaterResult
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult, PlanEnvelope
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord


class FineRiverPlanner:
    def plan(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput | GeoHydrologyPlanInput,
             surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], water: OpenWaterPlan,
             coarse: CoarseRiverPlan, control: PlanBuildControl) -> PlanBuildResult[FineRiverPlan]:
        return FineRiverJob().plan(world_uid=world_uid, inputs=inputs, surface_z=surface_z,
                                   water=water, coarse=coarse, control=control)

    def plan_fine(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                  water: PlanEnvelope[FineWaterResult], expected_water: PlanRef,
                  control: PlanBuildControl) -> PlanEnvelope[FineRiverPlan]:
        return FineRiverPublicationJob().publish(world_uid=world_uid, inputs=inputs,
            water=water, expected_water=expected_water, control=control)
