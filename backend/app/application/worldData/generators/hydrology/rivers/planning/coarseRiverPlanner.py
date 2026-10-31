"""Public coarse route operation; algorithms belong to the owning job."""
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.rivers.planning.coarse.execution import CoarseRiverJob
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.spatial.grid.coordinateTypes import FineZ, SurfaceGridCoord


class CoarseRiverPlanner:
    def plan(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput | GeoHydrologyPlanInput,
             surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], water: OpenWaterPlan,
             control: PlanBuildControl) -> PlanBuildResult[CoarseRiverPlan]:
        return CoarseRiverJob().plan(world_uid=world_uid, inputs=inputs,
                                    surface_z=surface_z, water=water, control=control)
