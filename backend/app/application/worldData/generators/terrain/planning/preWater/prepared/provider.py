"""Bind prepared natural geometry to exact registered upstream plans."""
from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.terrain.planning.preWater.terrainBasePlanner import PreWaterTerrainPlanner
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.natural.preparedTerrain import NaturalTerrainInputs, PreparedNaturalTerrain
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


class NaturalTerrainPlanProvider:
    def __init__(self, climate: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan],
                 terrain: RegisteredPlanContract[TerrainBaseInput, TerrainPlan]) -> None:
        self._climate, self._terrain = climate, terrain

    def build(self, request: PlanRequest[NaturalTerrainInputs], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[PreparedNaturalTerrain]:
        control.raise_if_shutdown()
        climate = dependencies.require(PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value), self._climate)
        terrain = dependencies.require(PlanSlot(SurfacePlanSlot.TERRAIN_BASE.value), self._terrain)
        if not any(d.slot == SurfacePlanSlot.CLIMATE_BASE.value and d.ref == climate.ref for d in terrain.dependencies):
            raise PlanBuildFailure((FieldPathError(("dependencies",), "natural preparation requires terrain's exact climate ref"),))
        base, relief, support = request.inputs
        return PreWaterTerrainPlanner().prepare_revision(request.key.world_uid, base, relief, support,
                                                         climate, terrain, control=control)
