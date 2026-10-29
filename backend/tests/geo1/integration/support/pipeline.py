"""Frozen contract fixtures; these do not activate production providers."""

from types import SimpleNamespace

from app.application.worldData.planning.contracts.surfacePlanningView import GeoSurfacePlanningView
from app.application.worldData.planning.contracts.surfacePlanBundle import GeoSurfacePlanBundle
from app.dataModel.hydrology.boundaries.attachedCoastline import CoastlineBoundaryInput, CoastlineBoundaryPlan
from app.dataModel.hydrology.enums.basinKind import BasinKind
from app.dataModel.hydrology.generation.waterGenerationDefaults import WaterGenerationDefaults
from app.dataModel.hydrology.generation.waterGenerationSettings import WorldWaterGenerationSettings
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan, GeoHydrologyRoutesPlan, HydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMapping
from app.dataModel.surfacePlanning.surfacePlanBindings import GEO_SURFACE_BINDINGS
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import GeoWaterPlacementPlan
from app.dataModel.terrain.regions.regionPlanningInput import TerrainRegionPlanningInput
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan, TerrainRegionsSnapshot
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceSupportPlan, CoatingPlan
from tests.geo1.coating.fixtures import prepared, coating_input
from tests.geo1.integration.support.fixtures import seal
from tests.geo1.support_sources.fixtures import captured
from tests.planning.consumers.test_wiring import capture, world


def fields(value):
    return {name: getattr(value, name) for name in type(value).model_fields}


def rebuild(value, **updates):
    return type(value).model_validate(fields(value) | updates)


def view():
    baseline = capture(world(world_uid="world", world_bounds=dict(x_min=0, x_max=1, y_min=0, y_max=1)))
    water = baseline.water_placement
    water_input = GeoWaterPlacementInput(**{name: getattr(water, name) for name in (
        "enabled", "resolution_mode", "default_water_level", "seas", "lakes", "anchors",
        "topology", "grid", "z_min", "z_max", "liquid_keys")},
        declared_world_bounds=water.topology.bounds, generation=WorldWaterGenerationSettings(),
        defaults=WaterGenerationDefaults(), sources=(), noise_policy=ContinentalNoisePolicy(),
        plate_policy=PlateGenerationPolicy(), composition_policy=FieldCompositionPolicy(),
        selection_policy=WaterFieldSelectionPolicy())
    return GeoSurfacePlanningView(**{name: getattr(baseline, name) for name in (
        "world_uid", "revision", "climate_base", "terrain_base", "relief", "river_relief",
        "hydrology_final", "climate_local", "capture_diagnostics")},
        water_placement=water_input,
        hydrology=GeoHydrologyPlanInput(**fields(baseline.hydrology), allowed_body_kinds=frozenset(BasinKind)),
        region_input=TerrainRegionPlanningInput(declared_world_bounds=water.topology.bounds,
            topology=water.topology, grid=water.grid, regions=(), anchors=water.anchors),
        boundary_input=CoastlineBoundaryInput(sources=(), resolution_mode=water.resolution_mode,
            topology=water.topology, grid=water.grid),
        surface_support=captured(seed=baseline.terrain_base.seed, topology=water.topology, grid=water.grid),
        coating_input=coating_input())


def bundle(inputs):
    _, evidence = prepared()
    common = evidence.hydrology.payload
    mapping = SourceBodyMapping(entries=())
    routes = HydrologyRoutesPlan(coarse_open_water=(), water_bodies=(), physical_unions=(),
        coarse_routes=(), fine_routes=(), fine_base_surface_z=(), declared_paint=common.declared_paint)
    payloads = {name: getattr(evidence, name).payload for name in (
        "climate_base", "terrain_base", "relief", "river_relief", "climate_local")}
    payloads.update(
        terrain_regions=TerrainRegionPlan(snapshot=TerrainRegionsSnapshot(world_uid=inputs.world_uid,
            snapshot_uid="regions", world_region=None, regions=()), coverages=()),
        water_placement=GeoWaterPlacementPlan(coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID,
            topology=inputs.water_placement.topology, records=(), basin_specs=(), outcomes=(),
            metadata=(), source_decisions=(), budget=None),
        hydrology_routes=GeoHydrologyRoutesPlan(base=routes, source_mapping=mapping, classification_decisions=()),
        hydrology=GeoHydrologyPlan(**fields(common), source_mapping=mapping, classification_decisions=()),
        coastline_boundaries=CoastlineBoundaryPlan(boundaries=(), outcomes=()),
        surface_support=SurfaceSupportPlan(facts=()), coating=CoatingPlan(cells=()))
    envelopes = {}
    for declaration in GEO_SURFACE_BINDINGS:
        name = declaration.slot.value
        envelopes[name] = seal(SimpleNamespace(metadata=declaration.metadata), payloads[name],
            tuple((dep.value, envelopes[dep.value]) for dep in declaration.upstream))
    return GeoSurfacePlanBundle(world_uid=inputs.world_uid, view_revision=inputs.revision, **envelopes)


def placement_plan():
    from app.application.worldData.generators.hydrology.basinSpecFactory import basin_specs
    from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
    from app.dataModel.placement.intent import PlacementIdentity
    from app.dataModel.placement.prepared import PreparedPlacementV2
    from app.dataModel.placement.result import DisabledPlacement, ResolvedPlacementV2, UnresolvedPlacementV2, PlacementDiagnostic, PlacementIssueCode
    from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, PolicyReason
    from app.dataModel.policy.policyEnums import PolicyOperation, PolicyState, PolicyDisableReason
    from app.dataModel.terrain.designedWater.coverage.budget import WaterCoverageBudget, BodyCoverageAllocation
    from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind
    from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
    from tests.test_water_placement_adapter import context, prepare, resolve, basin

    ready = ObjectAdmissionDecision[DesignedWaterStrategyKind, WaterPolicyReason](operation=PolicyOperation.OBJECT_ADMISSION, state=PolicyState.READY,
        effective_priority=2, behavior=DesignedWaterStrategyKind.AUTHORED_REGION, reasons=(),
        waiting_supports=(), provenance=(), issues=())
    disabled = rebuild(ready, state=PolicyState.DISABLED, effective_priority=0, behavior=None,
        reasons=(PolicyReason[WaterPolicyReason](domain_reason=None, common_reason=PolicyDisableReason.ZERO_PRIORITY),))
    failed = rebuild(ready, state=PolicyState.UNRESOLVED, effective_priority=None, behavior=None,
        issues=(FieldPathError(path=("hydrology", "missing"), message="missing support"),))
    snapshot = context()
    preparation = prepare(basins=(basin(),), snapshot=snapshot)
    result, records = resolve(preparation, snapshot)
    original = result.results[0]
    prepared = PreparedPlacementV2(intent=original.prepared.intent, original_area=original.prepared.original_area,
        candidates=original.prepared.candidates, decision=ready)
    outcomes = (
        ResolvedPlacementV2(prepared=prepared, candidate_uid=original.candidate_uid),
        DisabledPlacement(identity=PlacementIdentity(world_uid="world", source_uid="off", region_uid="off"),
            reason=PolicyDisableReason.ZERO_PRIORITY, decision=disabled),
        UnresolvedPlacementV2(identity=PlacementIdentity(world_uid="world", source_uid="missing", region_uid="missing"),
            prepared=None, diagnostics=(PlacementDiagnostic(code=PlacementIssueCode.MISSING_DEPENDENCY,
                region_uid="missing", detail="missing support"),)))
    budget = WaterCoverageBudget(region_uid="region", area_fine2=100, target_fraction=0.5, target_fine2=50,
        authored_union_fine2=16, residual_fine2=34, allocations=(BodyCoverageAllocation(source_uid="basin",
            generation_region_uid="region", requested_fine2=16, allocated_fine2=16),))
    return GeoWaterPlacementPlan(coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID, topology=snapshot.topology,
        records=tuple(records), basin_specs=tuple(basin_specs(preparation, records)), outcomes=outcomes,
        metadata=tuple(entry.source for entry in preparation.entries),
        source_decisions=(("basin", ready), ("off", disabled), ("missing", failed)), budget=budget)


class ReliefSeam:
    """PC-computed evidence and exact GEO handles share one terrain implementation."""

    def __init__(self, pc):
        from app.application.cache.backends.memoryCache import MemoryCache
        from app.application.cache.service.cacheService import CacheService
        from app.application.planning.providers.planRegistry import PlanRegistry
        from app.application.planning.service.planningService import PlanningService
        from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import GeoReliefPlanProvider, GeoRiverReliefPlanProvider
        from app.application.worldData.planning.composition.planProviders import declared_binding
        from app.dataModel.cache.policy.cachePolicy import CachePolicy
        from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
        from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
        from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterPolicyReason
        from app.dataModel.hydrology.seas import HydrologySeasPolicy
        from app.dataModel.hydrology.sources.waterSourceMetadata import WaterSourceMetadata
        from app.dataModel.hydrology.sources.waterDesignSource import WaterDesignSourceKind
        from app.dataModel.placement.prepared import PreparedPlacementV2
        from app.dataModel.placement.result import ResolvedPlacementV2
        from app.dataModel.policy.policyDecision import ObjectAdmissionDecision
        from app.dataModel.policy.policyEnums import PolicyOperation, PolicyState
        from app.dataModel.planning.policy.planningExecutionPolicy import PlanningExecutionPolicy
        from app.dataModel.surfacePlanning.surfacePlanBindings import geo_surface_plan_binding
        from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot as S
        from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind as Strategy
        from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
        from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
        from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
        from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan
        from tests.geo1.integration.support.fixtures import FrozenUpstream

        self.world_uid = "climate-world"
        pc.water.inputs = pc.water.inputs.model_copy(update={"seas": HydrologySeasPolicy(placement_specificity=2)})
        self.inputs = pc.inputs.model_copy(update={"declared_mountains": (pc.peak(),)})
        pc.before = pc.get(self.inputs)
        self.expected = pc.before.payload
        self.registry, self.handles = PlanRegistry(), {}
        for slot, input_type, payload_type in (
            (S.CLIMATE_BASE, ClimateBaseInput, ClimateBasePlan), (S.TERRAIN_BASE, TerrainBaseInput, TerrainPlan),
            (S.WATER_PLACEMENT, GeoWaterPlacementInput, GeoWaterPlacementPlan), (S.RELIEF, ReliefPlanInput, ReliefPlan),
            (S.HYDROLOGY_ROUTES, GeoHydrologyPlanInput, GeoHydrologyRoutesPlan), (S.RIVER_RELIEF, RiverReliefInput, RiverReliefPlan)):
            self.handles[slot.value] = declared_binding(geo_surface_plan_binding(slot), input_type, payload_type)
        h = self.handles
        for name in ("climate_base", "terrain_base", "water_placement", "hydrology_routes"):
            self.registry.register(h[name], FrozenUpstream())
        self.registry.register(h["relief"], GeoReliefPlanProvider(h["climate_base"], h["terrain_base"], h["water_placement"]))
        self.registry.register(h["river_relief"], GeoRiverReliefPlanProvider(h["relief"], h["hydrology_routes"]))
        self.upstream = {}
        climate = self.seal("climate_base", pc.water.terrain.climate.get().payload)
        terrain = self.seal("terrain_base", pc.water.terrain.get().payload, (("climate_base", climate),))
        water = pc.water.get().payload
        decisions, outcomes, metadata = [], [], []
        specs = {spec.source_uid: spec for spec in water.basin_specs}
        for record in water.records:
            spec = specs[record.source_uid]
            decision = ObjectAdmissionDecision[Strategy, WaterPolicyReason](operation=PolicyOperation.OBJECT_ADMISSION,
                state=PolicyState.READY, effective_priority=record.placement.effective_specificity,
                behavior=Strategy.AUTHORED_REGION, reasons=(), waiting_supports=(), provenance=(), issues=())
            prepared = record.placement.prepared
            outcomes.append(ResolvedPlacementV2(candidate_uid=record.placement.candidate_uid, prepared=PreparedPlacementV2(
                intent=prepared.intent, original_area=prepared.original_area, candidates=prepared.candidates, decision=decision)))
            decisions.append((record.source_uid, decision))
            metadata.append(WaterSourceMetadata(source_uid=spec.source_uid, source_kind=WaterDesignSourceKind.BASIN,
                body_kind=spec.kind, liquid=spec.liquid, level=spec.z_water_level, bands=spec.bands,
                source_path=("water_sources", spec.source_uid), default_depth=spec.z_water_level-spec.floor_z))
        payload = GeoWaterPlacementPlan(**fields(water), outcomes=tuple(outcomes), metadata=tuple(metadata),
            source_decisions=tuple(decisions), budget=None)
        self.upstream = dict(climate_base=climate, terrain_base=terrain,
            water_placement=self.seal("water_placement", payload, (("terrain_base", terrain),)))
        policy = CachePolicy(max_retained_bytes=10000000, max_entry_bytes=5000000)
        self.backend = MemoryCache(policy)
        self.service = PlanningService(self.registry, CacheService(self.backend, policy),
            PlanningExecutionPolicy(max_workers=2, max_pending_builds=8))

    def seal(self, name, payload, upstream=()):
        return seal(self.handles[name], payload, upstream, world_uid=self.world_uid)

    def build(self, name, inputs, available):
        from app.application.planning.providers.planRegistry import PlanDependencyReader
        from app.dataModel.planning.contracts.planDependency import PlanDependency
        from app.dataModel.planning.contracts.planRequest import PlanRequest
        from app.dataModel.planning.identity.planKey import PlanKey, WorldPlanScope
        from tests.geo1.integration.support.fixtures import Wait
        handle = self.handles[name]
        reader, deps = PlanDependencyReader(self.registry), []
        for declaration in handle.dependency_contracts:
            slot = declaration.slot
            reader = reader.with_plan(slot, self.handles[slot], available[slot])
            deps.append(PlanDependency(slot=slot, ref=available[slot].ref))
        deps, scope, meta = tuple(deps), WorldPlanScope(), handle.metadata
        request = PlanRequest[type(inputs)](key=PlanKey(world_uid=self.world_uid, scope=scope,
            contract_id=meta.id, schema_version=meta.schema_version, algorithm_version=meta.algorithm_version,
            input_fingerprint=handle.fingerprint_inputs(self.world_uid, scope, inputs, deps)), inputs=inputs, dependencies=deps)
        return self.service.get_or_build(handle, request, reader, wait=Wait())
