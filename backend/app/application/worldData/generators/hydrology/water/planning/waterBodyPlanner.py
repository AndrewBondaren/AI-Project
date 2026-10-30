"""Public hydrology operations; domain implementation belongs to owning jobs."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.water.planning.fineWaterJob import FineWaterJob
from app.application.worldData.generators.hydrology.water.planning.waterBodyJob import WaterBodyJob
from app.application.worldData.generators.hydrology.waterBodyAssembler import AssembledWater
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory as Category
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.worldHydrology import WorldHydrology
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope, PlanBuildResult
from app.dataModel.planning.diagnostics.planDiagnostic import PlanDiagnostic
from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord, FineZ
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan, GeoWaterPlacementPlan
from app.dataModel.terrain.relief.bathymetry.basinSpec import BasinSpec
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow
from app.dataModel.topology.worldTopology import WorldTopology


class WaterBodyPlanner:
    def fill_fine(self, surface: PlanEnvelope[FineSurfaceWindow], *, expected_surface: PlanRef,
                  topology: WorldTopology, specs: tuple[BasinSpec, ...],
                  policy: WorldHydrology, change_uid: EntityUid,
                  control: PlanBuildControl) -> tuple[SurfaceHeightmap, AssembledWater, tuple[PlanDiagnostic, ...]]:
        return FineWaterJob().fill(surface, expected_surface=expected_surface, topology=topology,
            specs=specs, policy=policy, change_uid=change_uid, control=control)

    def plan(self, *, world_uid: EntityUid, inputs: HydrologyPlanInput,
             surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], placement: WaterPlacementPlan,
             control: PlanBuildControl) -> PlanBuildResult[OpenWaterPlan]:
        return WaterBodyJob().plan(world_uid=world_uid, inputs=inputs, surface_z=surface_z,
                                   placement=placement, control=control)

    def plan_geo(self, *, world_uid: EntityUid, inputs: GeoHydrologyPlanInput,
                 surface_z: tuple[tuple[SurfaceGridCoord, FineZ], ...], placement: GeoWaterPlacementPlan,
                 classification_decisions: tuple[tuple[Category, HydrologyGenerationDecision], ...],
                 control: PlanBuildControl) -> PlanBuildResult[OpenWaterPlan]:
        return WaterBodyJob().plan_geo(world_uid=world_uid, inputs=inputs, surface_z=surface_z,
            placement=placement, classification_decisions=classification_decisions, control=control)
