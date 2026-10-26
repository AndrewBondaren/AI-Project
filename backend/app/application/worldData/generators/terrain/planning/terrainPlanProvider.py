"""Baseline coarse heights from captured terrain inputs and a climate base plan."""

from app.application.planning.providers.planProvider import RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.application.worldData.generators.terrain.noise import cell_z_noise
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.spatial.grid.coordinateTypes import FineZ, GridX, GridY, SurfaceGridCoord
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan


class TerrainPlanProvider:
    def __init__(self, climate_base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan]) -> None:
        self._climate_base = climate_base

    def build(self, request: PlanRequest[TerrainBaseInput], dependencies: PlanDependencyReader,
              control: PlanBuildControl) -> PlanBuildResult[TerrainPlan]:
        control.raise_if_shutdown()
        climate = dependencies.require(PlanSlot(SurfacePlanSlot.CLIMATE_BASE.value), self._climate_base).payload
        inputs = request.inputs
        surface: list[tuple[SurfaceGridCoord, FineZ]] = []
        for y in range(inputs.bbox.y_min, inputs.bbox.y_max + 1):
            control.raise_if_shutdown()
            for x in range(inputs.bbox.x_min, inputs.bbox.x_max + 1):
                gx, gy = GridX(x), GridY(y)
                sample = ClimatePlanSampler.sample(climate, gx, gy)
                z = max(inputs.z_min, min(inputs.z_max,
                    cell_z_noise(inputs.seed, gx, gy, sample.typical_elevation_z)))
                surface.append((SurfaceGridCoord(gx, gy), FineZ(z)))
        control.raise_if_shutdown()
        plan = TerrainPlan(bbox=inputs.bbox, surface_z=tuple(surface))
        return PlanBuildResult[TerrainPlan](payload=plan, diagnostics=())
