"""Lifecycle wiring for native policy, input binding and common water preparation."""

from collections.abc import Callable
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.hydrology.sources.proceduralSourceAdmission import ProceduralSourceAdmissionJob
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageAllocation import WaterCoverageAllocation
from app.application.worldData.generators.terrain.designedWater.preparation.proceduralWaterSourceAdapter import CapturedProceduralWaterInputs
from app.application.worldData.generators.terrain.designedWater.preparation.designPreparation import prepare_designed_water
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.placement.lifecycle.session import SupportReevaluation
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import PlacementBatchResultV2
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.terrain.designedWater.coverage.budget import WaterCoverageBudget
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan


def prepare_procedural_designed_water(
    inputs: GeoWaterPlacementInput, batch: PlacementBatchV2, *, water_intents: tuple[PlacementIntent, ...],
    pre_hydrology: PlanEnvelope[TerrainPlan], regions: TerrainRegionPlan, seed_root: EntityUid,
    prepare_competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2],
    strategies: DesignedWaterStrategyFactory, control: PlanBuildControl,
    reevaluate_support: SupportReevaluation | None = None,
) -> tuple[WaterCoverageBudget | None, tuple[WaterDesignPreparation, ...], PlacementBatchResultV2]:
    control.raise_if_shutdown()
    sources = ProceduralSourceAdmissionJob().resolve(inputs, batch, water_intents, control)
    ready_inputs = CapturedProceduralWaterInputs.capture(inputs, sources, pre_hydrology, regions, seed_root)
    requests = WaterCoverageAllocation().requests(sources, regions)
    return prepare_designed_water(sources.batch, water_intents=sources.water_intents, pre_hydrology=pre_hydrology,
        regions=regions, world_context=sources.world_context, coverage_requests=requests, authored_geometry=(),
        grid=inputs.grid, seed_root=seed_root, prepare_input=ready_inputs.prepare, prepare_competitor=prepare_competitor,
        strategies=strategies, selection_policy=inputs.selection_policy, control=control, reevaluate_support=reevaluate_support)
