"""Positive placement contracts; checked statically by Pyright."""

from typing import assert_type

from app.application.worldData.placement.lifecycle.session import PlacementSession, SupportReevaluation
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import PlacementBatchResultV2, PlacementOutcomeV2
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision

from tests.typing.planning.valid.policy import PolicyMode, PolicyReasonKind

from collections.abc import Callable
from app.application.planning.service.planningService import PlanBuildControl
from app.application.worldData.generators.terrain.designedWater.preparation.designPreparation import prepare_designed_water
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.input import WaterStrategyInput
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry


def valid_water_design_universe(batch: PlacementBatchV2, intents: tuple[PlacementIntent, ...],
    terrain: PlanEnvelope[TerrainPlan], grid: SurfaceGridSettings, control: PlanBuildControl,
    prepare: Callable[[PlacementAdmissionInput, WaterCoverageBudget | None], WaterStrategyInput],
    competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2],
    reevaluate: SupportReevaluation, selection: WaterFieldSelectionPolicy,
    regions: TerrainRegionPlan, world_context: ResolvedWaterGenerationContext,
    requests: tuple[BodyCoverageRequest, ...], geometries: tuple[AuthoredWaterGeometry, ...]) -> None:
    assert_type(prepare_designed_water(batch, water_intents=intents, pre_hydrology=terrain, grid=grid,
        seed_root="seed", prepare_input=prepare, prepare_competitor=competitor,
        regions=regions, world_context=world_context, coverage_requests=requests,
        authored_geometry=geometries,
        strategies=DesignedWaterStrategyFactory.builtins(), selection_policy=selection,
        control=control, reevaluate_support=reevaluate),
        tuple[WaterCoverageBudget | None, tuple[WaterDesignPreparation, ...], PlacementBatchResultV2])


def valid_placement_lifecycle(batch: PlacementBatchV2, header: PlacementHeader,
    prepared: PreparedPlacementV2, decision: ObjectAdmissionDecision[PolicyMode, PolicyReasonKind],
    reevaluate: SupportReevaluation) -> None:
    assert_type(PlacementAdmissionInput(header=header, decision=decision), PlacementAdmissionInput)
    session = PlacementSession.start(batch, reevaluate_support=reevaluate)
    assert_type(session.ready_for_preparation(), tuple[PlacementHeader, ...])
    session.submit(prepared)
    assert_type(session.step(), PlacementOutcomeV2 | None)
    assert_type(session.finish(), PlacementBatchResultV2)


from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometry, BoundaryGeometryResult
from app.application.worldData.generators.hydrology.boundaries.boundaryPlanner import CoastlineBoundaryPlanner
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer, PreparedCoastlineBoundary
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput, CoastlineBoundaryPlan
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot
from app.dataModel.hydrology.declaredCoastline import DeclaredCoastline
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.result import ResolvedPlacementV2


def valid_attached_boundary(source: DeclaredCoastline, snapshot: BoundaryWaterSnapshot,
                            admission: PlacementAdmissionInput, input: CoastlineBoundaryInput) -> None:
    assert_type(snapshot.accepted, tuple[ResolvedPlacementV2, ...])
    assert_type(BoundaryGeometry().prepare(source, snapshot), BoundaryGeometryResult)
    prepared = AttachedCoastlinePreparer().prepare_boundary(source, snapshot, admission)
    assert_type(prepared, PreparedCoastlineBoundary)
    assert_type(prepared.prepared, PreparedPlacementV2)
    assert_type(prepared.boundary.parts[0].path, tuple[HydrologyWaypoint, ...])
    assert_type(CoastlineBoundaryPlanner().prepare(input, snapshot, (admission,), snapshot_uid="dependent"), CoastlineBoundaryPlan)
