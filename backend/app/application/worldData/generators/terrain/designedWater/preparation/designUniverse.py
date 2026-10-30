"""Captured water-universe consistency; no policy execution, sampling or P2."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from pydantic import TypeAdapter
from app.application.planning.service.planningService import PlanBuildFailure
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterDesignDecision
from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.identity.uid import EntityUid
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.common import PlacementPhase
from app.dataModel.placement.intent import PlacementIntent
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput, WaterStrategyInput
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest, WaterCoverageBudget
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind, WaterDesignIssueCode
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan
from app.dataModel.topology.fineTopology import fine_topology
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.policy.policyEnums import PolicyState

_INPUT = TypeAdapter(WaterStrategyInput)
_ADMISSION = TypeAdapter(WaterDesignDecision)
_REQUESTS = TypeAdapter(tuple[BodyCoverageRequest, ...])
_GEOMETRY = TypeAdapter(tuple[AuthoredWaterGeometry, ...])


def invalid_water_design_input(message: str) -> PlanBuildFailure:
    return PlanBuildFailure((FieldPathError(("water_design", "universe"), message,
        code=WaterDesignIssueCode.INVALID_PREPARATION_INPUT.value),))


@dataclass(frozen=True)
class WaterDesignUniverse:
    batch: PlacementBatchV2
    pre_hydrology: PlanEnvelope[TerrainPlan]
    grid: SurfaceGridSettings
    seed_root: EntityUid
    regions: TerrainRegionPlan
    world_context: ResolvedWaterGenerationContext
    requests: tuple[BodyCoverageRequest, ...]
    geometries: tuple[AuthoredWaterGeometry, ...]
    selection_policy: WaterFieldSelectionPolicy
    by_region: Mapping[EntityUid, PlacementIntent]
    coverages: Mapping[EntityUid, RegionCoverage]
    geometry_by_source: Mapping[EntityUid, AuthoredWaterGeometry]
    authored_sources: frozenset[EntityUid]

    @classmethod
    def capture(cls, batch: PlacementBatchV2, *, water_intents: tuple[PlacementIntent, ...],
        pre_hydrology: PlanEnvelope[TerrainPlan], grid: SurfaceGridSettings, seed_root: EntityUid,
        regions: TerrainRegionPlan, world_context: ResolvedWaterGenerationContext,
        coverage_requests: tuple[BodyCoverageRequest, ...], authored_geometry: tuple[AuthoredWaterGeometry, ...],
        selection_policy: WaterFieldSelectionPolicy) -> "WaterDesignUniverse":
        batch = PlacementBatchV2.model_validate(batch, strict=True)
        pre_hydrology = PlanEnvelope[TerrainPlan].model_validate(pre_hydrology, strict=True)
        grid = SurfaceGridSettings.model_validate(grid, strict=True)
        selection_policy = WaterFieldSelectionPolicy.model_validate(selection_policy, strict=True)
        if (batch.phase is not PlacementPhase.PRE_RELIEF
                or batch.world_uid != pre_hydrology.ref.key.world_uid
                or batch.snapshot_revision != pre_hydrology.ref.output_fingerprint):
            raise invalid_water_design_input("design requires the same world/pre-relief terrain revision")
        bounds, bbox = batch.topology.bounds, pre_hydrology.payload.bbox
        if (bounds.x_min, bounds.x_max, bounds.y_min, bounds.y_max) != (
                bbox.x_min, bbox.x_max, bbox.y_min, bbox.y_max):
            raise invalid_water_design_input("design requires whole-scope terrain matching batch topology")
        intents = tuple(PlacementIntent.model_validate(intent, strict=True) for intent in water_intents)
        by_region = {intent.identity.region_uid: intent for intent in intents}
        if (len(by_region) != len(intents)
                or len({intent.identity.source_uid for intent in intents}) != len(intents)):
            raise invalid_water_design_input("water source and placement identities must be unique")
        admissions = {item.header.identity.region_uid: item for item in batch.objects}
        for uid, intent in by_region.items():
            if uid not in admissions or PlacementHeader.from_intent(intent) != admissions[uid].header:
                raise invalid_water_design_input("every water intent must retain its exact batch admission header")

        regions = TerrainRegionPlan.model_validate(regions, strict=True)
        requests = _REQUESTS.validate_python(coverage_requests, strict=True)
        snapshot = regions.snapshot
        if snapshot.world_uid != batch.world_uid or snapshot.snapshot_uid != batch.snapshot_uid:
            raise invalid_water_design_input("water budget requires the same region snapshot world and identity")
        coverages = {coverage.region_uid: coverage for coverage in regions.coverages}
        fine_bounds = fine_topology(batch.topology, grid.fine_span).bounds
        if any(not fine_bounds.contains(span.x0, span.y) or not fine_bounds.contains(span.x1 - 1, span.y)
                for coverage in regions.coverages for span in coverage.spans):
            raise invalid_water_design_input("water budget requires canonical world-fine region coverages")
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
            raise invalid_water_design_input("captured geometry requires unique admitted authored sources")
        if {request.source_uid for request in requests} != procedural_sources:
            raise invalid_water_design_input("coverage requests must identify exactly admitted procedural sources")
        if snapshot.world_region is None and procedural_sources:
            raise invalid_water_design_input("procedural coverage allocation requires explicit fixed world extent")
        for request in requests:
            region = snapshot.region_for(request.generation_region_uid)
            if region is None or region.generation_area_fine2 != request.generation_area_fine2:
                raise invalid_water_design_input("coverage request must retain the terrain-owned generation region and area")
        return cls(batch, pre_hydrology, grid, seed_root, regions, world_context, requests, geometries,
            selection_policy, MappingProxyType(by_region), MappingProxyType(coverages),
            MappingProxyType(geometry_by_source), frozenset(authored_sources))

    def owns(self, header: PlacementHeader) -> bool:
        return header.identity.region_uid in self.by_region

    def require_input(self, admission: PlacementAdmissionInput, value: WaterStrategyInput,
                      budget: WaterCoverageBudget | None) -> WaterStrategyInput:
        value = _INPUT.validate_python(value, strict=True)
        decision = _ADMISSION.validate_python(admission.decision, strict=True)
        header = admission.header
        if (value.pre_hydrology != self.pre_hydrology or value.topology != self.batch.topology
                or value.grid != self.grid or value.seed_root != self.seed_root
                or value.metadata.source_uid != header.identity.source_uid
                or decision.require_behavior() is not value.strategy):
            raise invalid_water_design_input("ready water input must retain batch terrain/topology/grid/seed/source/strategy")
        if (self.regions.snapshot.region_for(value.region.region_uid) != value.region
                or self.coverages.get(value.region.region_uid) != value.region_coverage):
            raise invalid_water_design_input("ready water input must retain the captured terrain region and coverage")
        if isinstance(value, AuthoredWaterDesignInput) and value.geometry != self.geometry_by_source.get(value.metadata.source_uid):
            raise invalid_water_design_input("authored input must reuse its captured coverage geometry")
        if value.strategy is not DesignedWaterStrategyKind.AUTHORED_REGION:
            allocation = next((a for a in budget.allocations if a.source_uid == value.metadata.source_uid), None) if budget else None
            request = next((r for r in self.requests if r.source_uid == value.metadata.source_uid), None)
            if allocation != value.budget or request is None or request.target_fraction != value.context.water_fraction:
                raise invalid_water_design_input("procedural input must retain its exact shared coverage allocation")
        return value
