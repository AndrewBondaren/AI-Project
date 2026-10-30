"""One coverage allocation, ready-source design and joint P2 (GEO-1 J04–J07)."""

from collections.abc import Callable

from pydantic import TypeAdapter

from app.application.planning.service.planningService import PlanBuildControl, PlanBuildFailure
from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.application.worldData.placement.diagnostics import diagnostic
from app.application.worldData.placement.lifecycle.session import PlacementSession, SupportReevaluation
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterDesignDecision
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.placement.result import PlacementBatchResultV2, PlacementIssueCode
from app.dataModel.policy.policyEnums import PolicyState
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput, WaterStrategyInput
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind, WaterDesignIssueCode
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

_INPUT = TypeAdapter(WaterStrategyInput)
_ADMISSION = TypeAdapter(WaterDesignDecision)
_REQUESTS = TypeAdapter(tuple[BodyCoverageRequest, ...])
_GEOMETRY = TypeAdapter(tuple[AuthoredWaterGeometry, ...])


def _invalid(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("water_design", "universe"), message,
        code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))


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
    """Design each ready water source once, in the same P2 session as competitors.

    The input owner supplies J01–J03 evidence and captured authored geometry.
    Terrain coverage operations measure the admitted union before allocation.
    J04 allocates once before J05 can construct any ready strategy input.
    Authored-only sources without fixed world extent retain no global budget.
    It receives the session's current decision after SUPPORT reevaluation. Neither
    callback resolves placement. The returned design results retain metadata,
    profiles and notices even for spatial losers; the common result retains every
    terminal outcome. No water placement record or production schema is projected.
    """
    control.raise_if_shutdown()
    batch = PlacementBatchV2.model_validate(batch, strict=True)
    pre_hydrology = PlanEnvelope[TerrainPlan].model_validate(pre_hydrology, strict=True)
    grid = SurfaceGridSettings.model_validate(grid, strict=True)
    selection_policy = WaterFieldSelectionPolicy.model_validate(selection_policy, strict=True)
    if (batch.phase is not PlacementPhase.PRE_RELIEF
            or batch.world_uid != pre_hydrology.ref.key.world_uid
            or batch.snapshot_revision != pre_hydrology.ref.output_fingerprint):
        raise _invalid("design requires the same world/pre-relief terrain revision")
    bounds, bbox = batch.topology.bounds, pre_hydrology.payload.bbox
    if (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max) != (
            bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max):
        raise _invalid("design requires whole-scope terrain matching batch topology")
    intents = tuple(PlacementIntent.model_validate(intent, strict=True) for intent in water_intents)
    by_region = {intent.identity.region_uid: intent for intent in intents}
    if (len(by_region) != len(intents)
            or len({intent.identity.source_uid for intent in intents}) != len(intents)):
        raise _invalid("water source and placement identities must be unique")
    admissions = {item.header.identity.region_uid: item for item in batch.objects}
    for uid, intent in by_region.items():
        if uid not in admissions or PlacementHeader.from_intent(intent) != admissions[uid].header:
            raise _invalid("every water intent must retain its exact batch admission header")

    regions = TerrainRegionPlan.model_validate(regions, strict=True)
    requests = _REQUESTS.validate_python(coverage_requests, strict=True)
    snapshot = regions.snapshot
    if snapshot.world_uid != batch.world_uid or snapshot.snapshot_uid != batch.snapshot_uid:
        raise _invalid("water budget requires the same region snapshot world and identity")
    coverages = {coverage.region_uid: coverage for coverage in regions.coverages}
    fine_bounds = fine_topology(batch.topology, grid.fine_span).bounds
    if any(not fine_bounds.contains(span.x0, span.y) or not fine_bounds.contains(span.x1 - 1, span.y)
            for coverage in regions.coverages for span in coverage.spans):
        raise _invalid("water budget requires canonical world-fine region coverages")
    procedural_sources: set[EntityUid] = set()
    authored_sources: set[EntityUid] = set()
    for uid, intent in by_region.items():
        decision = _ADMISSION.validate_python(admissions[uid].decision, strict=True)
        if decision.state in (PolicyState.READY, PolicyState.WAITING_SUPPORT):
            if decision.require_behavior() is not DesignedWaterStrategyKind.AUTHORED_REGION:
                procedural_sources.add(intent.identity.source_uid)
            else:
                authored_sources.add(intent.identity.source_uid)
    geometries = _GEOMETRY.validate_python(authored_geometry, strict=True)
    geometry_by_source = {geometry.source_uid: geometry for geometry in geometries}
    if len(geometry_by_source) != len(geometries) or not geometry_by_source.keys() <= authored_sources:
        raise _invalid("captured geometry requires unique admitted authored sources")
    if {request.source_uid for request in requests} != procedural_sources:
        raise _invalid("coverage requests must identify exactly admitted procedural sources")
    if snapshot.world_region is None and procedural_sources:
        raise _invalid("procedural coverage allocation requires explicit fixed world extent")
    for request in requests:
        region = snapshot.region_for(request.generation_region_uid)
        if region is None or region.generation_area_fine2 != request.generation_area_fine2:
            raise _invalid("coverage request must retain the terrain-owned generation region and area")
    control.raise_if_shutdown()
    session = PlacementSession.start(batch, reevaluate_support=reevaluate_support)
    pending_sources = {intent.identity.source_uid for uid, intent in by_region.items() if uid in session.queue.pending}
    if not authored_sources.intersection(pending_sources) <= geometry_by_source.keys():
        raise _invalid("pending authored sources require captured geometry before budget")
    requests = tuple(request for request in requests if request.source_uid in pending_sources)
    authored_coverages = []
    for geometry in geometries:
        if geometry.pre_hydrology_ref != pre_hydrology.ref:
            raise _invalid("authored coverage must retain its captured terrain revision")
        if geometry.source_uid not in pending_sources:
            continue
        control.raise_if_shutdown()
        coverage = RegionCoverageMeasure.from_cells(
            frozenset(cell for footprint in geometry.footprints for cell in footprint),
            region_uid=geometry.source_uid, space=geometry.coordinate_space, grid=grid)
        if any(not fine_bounds.contains(span.x0, span.y) or not fine_bounds.contains(span.x1 - 1, span.y)
                for span in coverage.spans):
            raise _invalid("authored coverage requires canonical native world geometry")
        authored_coverages.append(coverage)
    budget: WaterCoverageBudget | None = None
    if snapshot.world_region is not None:
        measure_uid = snapshot.world_region.region_uid
        authored_union = RegionCoverageMeasure.union(tuple(authored_coverages), region_uid=measure_uid)
        auto_union = RegionCoverageMeasure.union(tuple(coverages[request.generation_region_uid]
            for request in requests), region_uid=measure_uid)
        available = RegionCoverageMeasure.subtract(auto_union, authored_union, region_uid=measure_uid)
        budget = WaterCoverageBudgetPolicy().calculate(snapshot.world_region, world_context, requests,
            authored_union_fine2=RegionCoverageMeasure.area(authored_union),
            available_auto_area_fine2=RegionCoverageMeasure.area(available))
    allocations = {allocation.source_uid: allocation for allocation in budget.allocations} if budget is not None else {}
    requests_by_source = {request.source_uid: request for request in requests}

    preparer = DesignedWaterPlacementPreparer()
    designs: dict[EntityUid, WaterDesignPreparation] = {}

    def prepare_ready(headers: tuple[PlacementHeader, ...]) -> None:
        for header in headers:
            control.raise_if_shutdown()
            uid = header.identity.region_uid
            admission = session.objects[uid]
            try:
                if uid not in by_region:
                    session.submit(prepare_competitor(admission))
                    continue
                decision = _ADMISSION.validate_python(admission.decision, strict=True)
                value = _INPUT.validate_python(prepare_input(admission, budget), strict=True)
                if (value.pre_hydrology != pre_hydrology or value.topology != batch.topology
                        or value.grid != grid or value.seed_root != seed_root
                        or value.metadata.source_uid != header.identity.source_uid
                        or decision.require_behavior() is not value.strategy):
                    raise _invalid("ready water input must retain batch terrain/topology/grid/seed/source/strategy")
                if (snapshot.region_for(value.region.region_uid) != value.region
                        or coverages.get(value.region.region_uid) != value.region_coverage):
                    raise _invalid("ready water input must retain the captured terrain region and coverage")
                if isinstance(value, AuthoredWaterDesignInput) and value.geometry != geometry_by_source.get(value.metadata.source_uid):
                    raise _invalid("authored input must reuse its captured coverage geometry")
                if (value.strategy is not DesignedWaterStrategyKind.AUTHORED_REGION
                        and (allocations.get(value.metadata.source_uid) != value.budget
                             or requests_by_source[value.metadata.source_uid].target_fraction != value.context.water_fraction)):
                    raise _invalid("procedural input must retain its exact shared coverage allocation")
                control.raise_if_shutdown()
                draft = strategies.get(value.strategy).design(value)
                control.raise_if_shutdown()
                design = preparer.prepare(value, draft, selection_policy=selection_policy)
                prepared = preparer.bind_admission(value, design, intent=by_region[uid], admission=admission)
                session.submit(prepared)
                designs[uid] = design
            except PlanBuildFailure as failure:
                session.fail(header.identity, tuple(diagnostic(header, PlacementIssueCode.CONSTRAINT_VIOLATION,
                    f"{issue.code}: {issue.message}", path=issue.path) for issue in failure.issues))

    result = session.run(prepare_ready, check_cancelled=control.raise_if_shutdown)
    return budget, tuple(designs[uid] for uid in sorted(designs)), result
