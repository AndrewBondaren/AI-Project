"""Public pre-water terrain operation; no terrain algorithms in the planner."""

from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.planning.preWater.terrainBaseJob import PreWaterTerrainJob
from app.application.worldData.generators.terrain.planning.preWater.terrainWindowJob import PreWaterTerrainWindowJob
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.identity.uid import EntityUid
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput
from app.dataModel.topology.worldTopology import Coord
from app.dataModel.terrain.sampling.fineSurfaceWindow import FineSurfaceWindow


class PreWaterTerrainPlanner:
    def prepare_window(self, world_uid: EntityUid, base_input: TerrainBaseInput, relief_input: ReliefPlanInput,
                       support_input: SurfaceSupportInput, climate_base: PlanEnvelope[ClimateBasePlan],
                       terrain_base: PlanEnvelope[TerrainPlan], *, cells: RegionCoverage,
                       control: PlanBuildControl) -> PlanEnvelope[FineSurfaceWindow]:
        return PreWaterTerrainWindowJob().prepare(world_uid, base_input, relief_input, support_input,
                                                  climate_base, terrain_base, cells, control)

    def prepare(self, world_uid: EntityUid, base_input: TerrainBaseInput, relief_input: ReliefPlanInput,
                support_input: SurfaceSupportInput, climate_base: PlanEnvelope[ClimateBasePlan],
                terrain_base: PlanEnvelope[TerrainPlan], *, cells: RegionCoverage,
                control: PlanBuildControl) -> tuple[SurfaceHeightmap, frozenset[Coord]]:
        return PreWaterTerrainJob(world_uid, base_input, relief_input, support_input,
                                  climate_base, terrain_base, control).prepare(cells)
