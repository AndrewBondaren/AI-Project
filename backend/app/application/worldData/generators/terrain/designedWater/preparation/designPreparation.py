"""Lifecycle wiring for the shared water preparation jobs and common P2."""

from collections.abc import Callable
from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.preparation.designUniverse import WaterDesignUniverse
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageAllocation import WaterCoverageAllocation
from app.application.worldData.generators.terrain.designedWater.preparation.readyWaterDesign import ReadyWaterDesignJob
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.placement.diagnostics import preparation_diagnostics
from app.application.worldData.placement.lifecycle.session import PlacementSession, SupportReevaluation
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import PlacementBatchResultV2
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.input import WaterStrategyInput
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan


def prepare_designed_water(
    batch: PlacementBatchV2, *, water_intents: tuple[PlacementIntent, ...],
    pre_hydrology: PlanEnvelope[TerrainPlan], grid: SurfaceGridSettings, seed_root: EntityUid,
    regions: TerrainRegionPlan, world_context: ResolvedWaterGenerationContext,
    coverage_requests: tuple[BodyCoverageRequest, ...],
    authored_geometry: tuple[AuthoredWaterGeometry, ...],
    prepare_input: Callable[[PlacementAdmissionInput, WaterCoverageBudget | None], WaterStrategyInput],
    prepare_competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2],
    strategies: DesignedWaterStrategyFactory, selection_policy: WaterFieldSelectionPolicy,
    control: PlanBuildControl, reevaluate_support: SupportReevaluation | None = None,
) -> tuple[WaterCoverageBudget | None, tuple[WaterDesignPreparation, ...], PlacementBatchResultV2]:
    control.raise_if_shutdown()
    universe = WaterDesignUniverse.capture(batch, water_intents=water_intents, pre_hydrology=pre_hydrology,
        grid=grid, seed_root=seed_root, regions=regions, world_context=world_context,
        coverage_requests=coverage_requests, authored_geometry=authored_geometry, selection_policy=selection_policy)
    session = PlacementSession.start(universe.batch, reevaluate_support=reevaluate_support)
    budget = WaterCoverageAllocation().allocate(universe, session.queue.pending, control)
    ready_job = ReadyWaterDesignJob(universe, strategies, control)
    designs: dict[EntityUid, WaterDesignPreparation] = {}

    def prepare_ready(headers: tuple[PlacementHeader, ...]) -> None:
        for header in headers:
            control.raise_if_shutdown()
            admission = session.objects[header.identity.region_uid]
            try:
                if universe.owns(header):
                    design, prepared = ready_job.prepare(admission, prepare_input(admission, budget), budget)
                    designs[header.identity.region_uid] = design
                else:
                    prepared = prepare_competitor(admission)
                session.submit(prepared)
            except PlanBuildFailure as failure:
                session.fail(header.identity, preparation_diagnostics(header, failure.issues))

    result = session.run(prepare_ready, check_cancelled=control.raise_if_shutdown)
    return budget, tuple(designs[uid] for uid in sorted(designs)), result
