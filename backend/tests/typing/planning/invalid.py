"""Every marked line must produce its specified pyright diagnostic."""

from app.application.worldData.masks.collection.defaultCollect import MaskSourceCollector, default_collect
from app.application.worldData.generators.terrain.landcover.types import LandcoverCollectContext
from app.dataModel.masks.maskCategoryPolicy import MaskCategoryPolicy
from app.application.worldData.generators.terrain.landcover.materializer import LandcoverMaterializer
from app.application.worldData.pack.bake.lightGrid.bakeContext import LightGridBakeContext


def invalid_landcover_pack_scope(materializer: LandcoverMaterializer, ctx: LightGridBakeContext,
                                 policy: MaskCategoryPolicy) -> None:
    materializer.collect(ctx, policy)  # EXPECT: reportArgumentType
    materializer.apply  # EXPECT: reportAttributeAccessIssue


def invalid_collection_context_variance(
    collector: MaskSourceCollector[LandcoverCollectContext, int],
) -> MaskSourceCollector[object, int]:
    return collector  # EXPECT: reportReturnType


def invalid_collection_spec_variance(
    collector: MaskSourceCollector[object, int],
) -> MaskSourceCollector[object, object]:
    return collector  # EXPECT: reportReturnType


def invalid_collection_context(collector: MaskSourceCollector[int, int], policy: MaskCategoryPolicy) -> None:
    default_collect(collector, "wrong context", policy, key=lambda value: value)  # EXPECT: reportArgumentType

from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.application.cache.contracts.cacheBackend import CacheBinding
from app.application.cache.service.cacheService import CacheService
from app.application.planning.providers.planProvider import PlanProvider, RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planningService import PlanningService, PlanWaitControl
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.application.encoding.canonicalCodec import decode
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.application.worldData.generators.terrain.planning.terrainPlanProvider import TerrainPlanProvider
from app.application.worldData.generators.terrain.planning.waterPlacementPlanProvider import WaterPlacementPlanProvider
from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import ReliefPlanProvider, RiverReliefPlanProvider
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.dataModel.spatial.grid.coordinateTypes import GridX, GridY
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope, PlanBuildResult
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import InputFingerprint, OutputFingerprint, SchemaVersion
from app.dataModel.cache.contracts.cacheContract import CacheSchemaVersion
from app.dataModel.spatial.grid.coordinateTypes import FineX
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan, RiverBedRecord
from app.dataModel.spatial.grid.coordinateTypes import FineXY, SurfaceGridCoord
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, HydrologyRoutesPlan, RiverRoute
from tests.typing.planning.valid.infrastructure import ClimateInput, ClimatePayload, HydroInput, HydroPayload, build_climate, require_climate, require_grid_x


def invalid_cache_entry(key: CacheKey[PlanEnvelope[HydroPayload]], envelope: PlanEnvelope[ClimatePayload]) -> None:
    CacheEntry[PlanEnvelope[ClimatePayload]](key=key, value=envelope)  # EXPECT: reportArgumentType


def invalid_request(request: PlanRequest[HydroInput]) -> None:
    build_climate(request)  # EXPECT: reportArgumentType


def invalid_dependency(envelope: PlanEnvelope[HydroPayload]) -> None:
    require_climate(envelope)  # EXPECT: reportArgumentType


def invalid_unit(value: FineX) -> None:
    require_grid_x(value)  # EXPECT: reportArgumentType


def invalid_mutation(envelope: PlanEnvelope[ClimatePayload]) -> None:
    envelope.payload.temperatures[0] = 10  # EXPECT: reportIndexIssue


def invalid_invariant_contract(contract: CacheContract[PlanEnvelope[ClimatePayload]]) -> CacheContract[object]:
    return contract  # EXPECT: reportReturnType


def invalid_digest(value: OutputFingerprint) -> InputFingerprint:
    return value  # EXPECT: reportReturnType


def invalid_version(value: CacheSchemaVersion) -> SchemaVersion:
    return value  # EXPECT: reportReturnType


def invalid_climate_phase(local: PlanEnvelope[ClimateLocalPlan], key: CacheKey[PlanEnvelope[ClimateBasePlan]]) -> None:
    CacheEntry[PlanEnvelope[ClimateBasePlan]](key=key, value=local)  # EXPECT: reportArgumentType


def invalid_terrain_payload(terrain: PlanEnvelope[TerrainPlan], key: CacheKey[PlanEnvelope[ClimateBasePlan]]) -> None:
    CacheEntry[PlanEnvelope[ClimateBasePlan]](key=key, value=terrain)  # EXPECT: reportArgumentType


def invalid_relief_phase(relief: PlanEnvelope[ReliefPlan], key: CacheKey[PlanEnvelope[RiverReliefPlan]]) -> None:
    CacheEntry[PlanEnvelope[RiverReliefPlan]](key=key, value=relief)  # EXPECT: reportArgumentType


def invalid_river_bed_space(bed: RiverBedRecord[FineXY]) -> RiverBedRecord[SurfaceGridCoord]:
    return bed  # EXPECT: reportReturnType


def invalid_hydrology_phase(routes: PlanEnvelope[HydrologyRoutesPlan], key: CacheKey[PlanEnvelope[HydrologyPlan]]) -> None:
    CacheEntry[PlanEnvelope[HydrologyPlan]](key=key, value=routes)  # EXPECT: reportArgumentType


def invalid_route_space(route: RiverRoute[SurfaceGridCoord]) -> RiverRoute[FineXY]:
    return route  # EXPECT: reportReturnType


def invalid_service_binding(service: CacheService, binding: CacheBinding[ClimatePayload],
                            key: CacheKey[HydroPayload], entry: CacheEntry[HydroPayload]) -> None:
    service.get(binding, key)  # EXPECT: reportArgumentType
    service.put(binding, entry)  # EXPECT: reportArgumentType
    service.evict(binding, key)  # EXPECT: reportArgumentType


def invalid_planning_bindings(service: PlanningService, registry: PlanRegistry,
                               contract: RegisteredPlanContract[ClimateInput, ClimatePayload],
                               provider: PlanProvider[HydroInput, HydroPayload],
                               request: PlanRequest[HydroInput], reader: PlanDependencyReader,
                               wait: PlanWaitControl) -> PlanEnvelope[HydroPayload]:
    registry.register(contract, provider)  # EXPECT: reportArgumentType
    service.get_or_build(contract, request, reader, wait=wait)  # EXPECT: reportArgumentType
    return reader.require(PlanSlot("climate"), contract)  # EXPECT: reportReturnType


def invalid_decode_type(encoded: bytes, manifest: CanonicalSchemaManifest) -> ClimatePayload:
    return decode(encoded, HydroPayload, manifest)  # EXPECT: reportReturnType


def invalid_climate_sampler_domain(plan: HydrologyPlan) -> None:
    ClimatePlanSampler.sample(plan, GridX(0), GridY(0))  # EXPECT: reportArgumentType


def invalid_terrain_climate_dependency(contract: RegisteredPlanContract[ClimateBaseInput, ClimateLocalPlan]) -> None:
    TerrainPlanProvider(contract)  # EXPECT: reportArgumentType


def invalid_water_terrain_dependency(contract: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan]) -> None:
    WaterPlacementPlanProvider(contract)  # EXPECT: reportArgumentType


def invalid_surface_slot_assignment(value: PlanSlot) -> SurfacePlanSlot:
    return value  # EXPECT: reportReturnType


def invalid_relief_climate_dependency(local: RegisteredPlanContract[ClimateBaseInput, ClimateLocalPlan],
    terrain: RegisteredPlanContract[TerrainBaseInput, TerrainPlan],
    water: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan]) -> None:
    ReliefPlanProvider(local, terrain, water)  # EXPECT: reportArgumentType


def invalid_river_relief_phase(relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
    final: RegisteredPlanContract[HydrologyPlanInput, HydrologyPlan]) -> None:
    RiverReliefPlanProvider(relief, final)  # EXPECT: reportArgumentType


from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import HydrologyRoutesPlanProvider, HydrologyFinalPlanProvider
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import RiverReliefInput
from app.application.planning.service.planningService import PlanBuildControl


def invalid_hydrology_providers(relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
    water: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan],
    routes: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan],
    final: RegisteredPlanContract[HydrologyFinalInput, HydrologyPlan],
    routes_assembler: HydrologyRoutesAssembler, facts_assembler: HydrologyFactsAssembler,
    provider: HydrologyFinalPlanProvider, request: PlanRequest[HydrologyPlanInput],
    reader: PlanDependencyReader, control: PlanBuildControl) -> None:
    HydrologyRoutesPlanProvider(final, water, routes_assembler)  # EXPECT: reportArgumentType
    HydrologyFinalPlanProvider(relief, final, relief, facts_assembler)  # EXPECT: reportArgumentType (2)
    provider.build(request, reader, control)  # EXPECT: reportArgumentType


from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan, RiverRouteBatch


def invalid_stage_batch_space(batch: RiverRouteBatch[FineXY]) -> CoarseRiverPlan:
    return batch  # EXPECT: reportReturnType


def invalid_fine_stage_route(route: RiverRoute[SurfaceGridCoord]) -> None:
    FineRiverPlan(routes=(route,), base_surface_z=())  # EXPECT: reportArgumentType


def invalid_coarse_stage_claim(batch: RiverRouteBatch[FineXY]) -> None:
    CoarseRiverPlan(routes=(), claims=batch.claims)  # EXPECT: reportArgumentType


from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.hydrology.load.paint.declaredWaterPaintProjector import DeclaredWaterPaintProjector
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyAnchorInput


def invalid_water_owner_input(owner: WaterBodyPlanner, inputs: HydrologyFinalInput,
    placement: WaterPlacementPlan, control: PlanBuildControl) -> None:
    owner.plan(world_uid="world", inputs=inputs, surface_z=(), placement=placement, control=control)  # EXPECT: reportArgumentType


def invalid_water_owner_phase(owner: WaterBodyPlanner, inputs: HydrologyPlanInput,
    placement: WaterPlacementPlan, control: PlanBuildControl) -> PlanBuildResult[HydrologyPlan]:
    return owner.plan(world_uid="world", inputs=inputs, surface_z=(), placement=placement, control=control)  # EXPECT: reportReturnType


def invalid_paint_owner_declarations(owner: DeclaredWaterPaintProjector, anchors: tuple[HydrologyAnchorInput, ...]) -> None:
    owner.project(rivers=anchors, coastlines=(), lakes=(), anchors=anchors)  # EXPECT: reportArgumentType


from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan


def invalid_coarse_owner_input(owner: CoarseRiverPlanner, inputs: HydrologyFinalInput,
    water: OpenWaterPlan, control: PlanBuildControl) -> None:
    owner.plan(world_uid="world", inputs=inputs, surface_z=(), water=water, control=control)  # EXPECT: reportArgumentType


def invalid_fine_owner_dependency(owner: FineRiverPlanner, inputs: HydrologyPlanInput,
    water: OpenWaterPlan, fine: FineRiverPlan, control: PlanBuildControl) -> None:
    owner.plan(world_uid="world", inputs=inputs, surface_z=(), water=water, coarse=fine, control=control)  # EXPECT: reportArgumentType


def invalid_coarse_owner_phase(owner: CoarseRiverPlanner, inputs: HydrologyPlanInput,
    water: OpenWaterPlan, control: PlanBuildControl) -> PlanBuildResult[FineRiverPlan]:
    return owner.plan(world_uid="world", inputs=inputs, surface_z=(), water=water, control=control)  # EXPECT: reportReturnType


from app.dataModel.terrain.relief.planning.reliefPlan import RiverReliefPlan


def invalid_routes_assembly_dependency(owner: HydrologyRoutesAssembler, inputs: HydrologyPlanInput,
    relief: RiverReliefPlan, placement: WaterPlacementPlan, control: PlanBuildControl) -> None:
    owner.assemble(world_uid="world", inputs=inputs, relief=relief, placement=placement, control=control)  # EXPECT: reportArgumentType


def invalid_facts_assembly_phase(owner: HydrologyFactsAssembler, inputs: HydrologyFinalInput,
    relief: ReliefPlan, routes: HydrologyPlan, river: RiverReliefPlan, control: PlanBuildControl) -> None:
    owner.assemble(inputs=inputs, relief=relief, routes=routes, river=river, control=control)  # EXPECT: reportArgumentType


from app.application.worldData.generators.climate.planning.climatePlanProvider import ClimateLocalPlanProvider
from app.application.worldData.generators.climate.localFieldFromCoarse import build_local_plan_from_coarse
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput


def invalid_local_request(provider: ClimateLocalPlanProvider, request: PlanRequest[ClimateBaseInput],
    reader: PlanDependencyReader, control: PlanBuildControl) -> None:
    provider.build(request, reader, control)  # EXPECT: reportArgumentType


def invalid_local_surface(inputs: ClimateLocalInput, base: ClimateBasePlan, relief: ReliefPlan) -> None:
    build_local_plan_from_coarse(inputs, base, relief)  # EXPECT: reportArgumentType


def invalid_local_result(provider: ClimateLocalPlanProvider, request: PlanRequest[ClimateLocalInput],
    reader: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[ClimateBasePlan]:
    return provider.build(request, reader, control)  # EXPECT: reportReturnType


from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningView


def invalid_surface_request(assembler: SurfacePlanningAssembler, bundle: SurfacePlanBundle, wait: PlanWaitControl) -> None:
    assembler.prepare(bundle, wait=wait)  # EXPECT: reportArgumentType


from app.application.worldData.regions.factConsumers.context import FactConsumerContext


def invalid_removed_observation_inputs(ctx: FactConsumerContext, bake: LightGridBakeContext) -> None:
    FactConsumerContext(cells=(), surface=None)  # EXPECT: reportCallIssue
    FactConsumerContext(cells=(), local_field=None)  # EXPECT: reportCallIssue
    FactConsumerContext(cells=(), climate_profiles={})  # EXPECT: reportCallIssue
    FactConsumerContext(cells=(), relief_z={})  # EXPECT: reportCallIssue
    FactConsumerContext(cells=(), hydro={})  # EXPECT: reportCallIssue
    FactConsumerContext(cells=(), surface_z={})  # EXPECT: reportCallIssue
    ctx.surface  # EXPECT: reportAttributeAccessIssue
    bake.surface_planning  # EXPECT: reportAttributeAccessIssue


def invalid_surface_final_as_routes(bundle: SurfacePlanBundle) -> PlanEnvelope[HydrologyRoutesPlan]:
    return bundle.hydrology  # EXPECT: reportReturnType




def invalid_surface_working(working: SurfaceWorkingMaps, gx: GridX, gy: GridY) -> None:
    working.terrain.relief_z[(gx, gy)] = 1  # EXPECT: reportIndexIssue
    working.hydrology.fine_z_for_tile(gx, gy)[(gx, gy)] = 1  # EXPECT: reportIndexIssue
    working.climate = working.climate  # EXPECT: reportAttributeAccessIssue
    working.climate.sample_pole(1, 2)  # EXPECT: reportArgumentType (2)


from tests.typing.planning.valid.policy import OtherPolicyMode, OtherPolicyReason, PolicyDefaults, PolicyFacts, PolicyMode, PolicyReasonKind, PolicySettings
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.policy.objectAdmissionPolicyDefinition import EnabledGate
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, ValueSelectionDecision
from app.dataModel.policy.policyEnums import PolicyOperation, PolicyRuleId, PolicyStage, RulePrecedence
from app.dataModel.policy.policyReferences import (
    DirectValueRef, FactValueRef, PriorityValueRef,
)
from app.dataModel.policy.policyRules import (
    Equal, PolicyRule, SelectBehaviorEffect,
)
from app.dataModel.policy.policySpec import (
    ObjectAdmissionPolicySpec, ValueSelectionPolicySpec,
)


def invalid_policy_field_pairs(flag: DirectValueRef[PolicySettings, bool],
    fact: FactValueRef[PolicyFacts, bool], mode: DirectValueRef[PolicySettings, PolicyMode]) -> None:
    Equal[PolicySettings, bool](flag, 1)  # EXPECT: reportArgumentType
    Equal[PolicySettings, PolicyMode](mode, OtherPolicyMode.OTHER)  # EXPECT: reportArgumentType
    FactValueRef[PolicySettings, bool](FieldRef(lambda: PolicySettings, lambda s: s.enabled))  # EXPECT: reportArgumentType
    DirectValueRef[PolicyFacts, bool](FieldRef(lambda: PolicyFacts, lambda f: f.flag))  # EXPECT: reportArgumentType
    PriorityValueRef[PolicySettings](FieldRef(lambda: PolicySettings, lambda s: s.mode))  # EXPECT: reportArgumentType
    EnabledGate[PolicySettings](mode)  # EXPECT: reportArgumentType


def invalid_policy_rule_domains() -> None:
    PolicyRule[PolicyMode, PolicyReasonKind](id=PolicyRuleId("foreign"), stage=PolicyStage.BEHAVIOR,
        precedence=RulePrecedence(1), conditions=(), effect=SelectBehaviorEffect(OtherPolicyMode.OTHER))  # EXPECT: reportArgumentType
    PolicyRule[PolicyMode, PolicyReasonKind](id=PolicyRuleId("reason"), stage=PolicyStage.BEHAVIOR,
        precedence=RulePrecedence(1), conditions=(), effect=SelectBehaviorEffect(PolicyMode.FIRST),
        domain_reason=OtherPolicyReason.OTHER)  # EXPECT: reportArgumentType
    PolicyRule[PolicyMode, PolicyReasonKind](id=PolicyRuleId("priority"), stage=PolicyStage.BEHAVIOR,
        precedence=1, conditions=(), effect=SelectBehaviorEffect(PolicyMode.FIRST))  # EXPECT: reportArgumentType


def invalid_policy_operations(priority: PriorityValueRef[PolicyDefaults]) -> None:
    ValueSelectionPolicySpec[PolicyMode, PolicyReasonKind](operation=PolicyOperation.VALUE_SELECTION,
        rules=(), expected_behavior_type=PolicyMode, fallback_rules=(), authored_priority_ref=priority)  # EXPECT: reportCallIssue
    ObjectAdmissionPolicySpec[PolicyMode, PolicyReasonKind](operation=PolicyOperation.VALUE_SELECTION,  # EXPECT: reportArgumentType
        rules=(), authored_priority_ref=priority, domain_priority_ref=priority, terminal_priority_ref=priority,
        expected_behavior_type=PolicyMode, fallback_rules=())


def invalid_selection_as_admission(value: ValueSelectionDecision[PolicyMode, PolicyReasonKind]
    ) -> ObjectAdmissionDecision[PolicyMode, PolicyReasonKind]:
    return value  # EXPECT: reportReturnType


def invalid_behavior_decision(value: ObjectAdmissionDecision[OtherPolicyMode, PolicyReasonKind]
    ) -> ObjectAdmissionDecision[PolicyMode, PolicyReasonKind]:
    return value  # EXPECT: reportReturnType


def invalid_policy_result_mutation(value: ObjectAdmissionDecision[PolicyMode, PolicyReasonKind]) -> None:
    value.behavior = PolicyMode.SECOND  # EXPECT: reportAttributeAccessIssue
    value.effective_priority = 0  # EXPECT: reportAttributeAccessIssue


from app.application.policy.policyResolver import PolicyResolver
from app.dataModel.policy.policyBindings import PolicyFacts as PolicyObservations, PolicyInputs, PolicySource
from app.dataModel.validation.enums.resolutionMode import ResolutionMode


def invalid_policy_execution(settings: PolicySettings, defaults: PolicyDefaults,
    value_spec: ValueSelectionPolicySpec[PolicyMode, PolicyReasonKind],
    prior: ObjectAdmissionDecision[PolicyMode, PolicyReasonKind]) -> None:
    PolicySource[PolicySettings](PolicySettings, defaults, ())  # EXPECT: reportArgumentType
    PolicySource[PolicySettings](PolicyDefaults, settings, ())  # EXPECT: reportArgumentType
    PolicyResolver().resolve(value_spec, PolicyInputs(), PolicyObservations(), mode=ResolutionMode.RUNTIME, resume=prior)  # EXPECT: reportArgumentType
    PolicyResolver().resolve(value_spec, PolicyInputs(), PolicyObservations(), mode="runtime")  # EXPECT: reportCallIssue; EXPECT: reportArgumentType


from app.application.worldData.placement.lifecycle.session import PlacementSession
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.lifecycle.header import PlacementHeader
from app.dataModel.placement.prepared import PreparedPlacement
from app.dataModel.placement.result import PlacementOutcomeV2


def invalid_lifecycle_operation(header: PlacementHeader,
    value: ValueSelectionDecision[PolicyMode, PolicyReasonKind], session: PlacementSession,
    legacy: PreparedPlacement, outcome: PlacementOutcomeV2) -> None:
    PlacementAdmissionInput(header=header, decision=value)  # EXPECT: reportArgumentType
    session.submit(legacy)  # EXPECT: reportArgumentType
    outcome.prepared  # EXPECT: reportAttributeAccessIssue


from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision, WaterPolicyReason
from app.dataModel.hydrology.enums.planning.hydrologyExecutionMode import HydrologyExecutionMode


def invalid_hydrology_generation(decision: HydrologyGenerationDecision) -> None:
    mode: HydrologyExecutionMode = True  # EXPECT: reportAssignmentType
    admission: ObjectAdmissionDecision[HydrologyExecutionMode, WaterPolicyReason] = decision  # EXPECT: reportAssignmentType


from app.dataModel.policy.declarations.fieldPolicy import SelectByValue, ValueCase
from app.dataModel.policy.declarations.policyDeclaration import ValuePolicy
from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from tests.typing.planning.valid.policy import DeclarationOwner, VALUE_DECLARATION


def invalid_policy_declarations() -> None:
    ValueCase[bool, PolicyMode, PolicyReasonKind](when=False, behavior=OtherPolicyMode.OTHER)  # EXPECT: reportArgumentType
    ValueCase[bool, PolicyMode, PolicyReasonKind](when=False, behavior=PolicyMode.FIRST, reason=OtherPolicyReason.OTHER)  # EXPECT: reportArgumentType
    ValueCase[bool, PolicyMode, PolicyReasonKind](when="false", behavior=PolicyMode.FIRST)  # EXPECT: reportArgumentType
    ValueCase[list[int], PolicyMode, PolicyReasonKind](when=[], behavior=PolicyMode.FIRST)  # EXPECT: reportInvalidTypeArguments
    ValuePolicy[PolicyMode, PolicyReasonKind](owner=DeclarationOwner, behavior_type=OtherPolicyMode, reason_type=PolicyReasonKind)  # EXPECT: reportArgumentType
    SelectByValue[bool, PolicyMode, PolicyReasonKind](VALUE_DECLARATION, [])  # EXPECT: reportArgumentType
    PolicyCaseDeclaration[PolicyMode, PolicyReasonKind](key=PolicyMode.FIRST, conditions=(), effect=SelectBehaviorEffect(OtherPolicyMode.OTHER))  # EXPECT: reportArgumentType


from app.application.policy.declarations.compiler import compile_value_policy, compile_admission_policy
from app.dataModel.policy.declarations.policyDeclaration import AdmissionPolicy


def invalid_policy_compilation(admission: AdmissionPolicy[PolicyMode, PolicyReasonKind]) -> None:
    compile_admission_policy(VALUE_DECLARATION, ())  # EXPECT: reportArgumentType
    compile_value_policy(admission, ())  # EXPECT: reportArgumentType
    compile_value_policy(VALUE_DECLARATION, (PolicySettings(enabled=True, priority=0, mode=PolicyMode.FIRST),))  # EXPECT: reportArgumentType
    compile_value_policy(VALUE_DECLARATION, [PolicySettings])  # EXPECT: reportArgumentType


from app.dataModel.hydrology.policy.hydrologyPolicyDefinition import HYDROLOGY_GENERATION_POLICY


def invalid_hydrology_metadata() -> None:
    SelectByValue[bool, OtherPolicyMode, WaterPolicyReason](HYDROLOGY_GENERATION_POLICY, ())  # EXPECT: reportArgumentType
    foreign: ValueSelectionPolicySpec[OtherPolicyMode, WaterPolicyReason] = compile_value_policy(HYDROLOGY_GENERATION_POLICY, ())  # EXPECT: reportAssignmentType


from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.application.worldData.generators.terrain.regions.regionExtent import prepare_terrain_regions
from app.dataModel.terrain.regions.coverageGeometry import CoverageSpan, RegionCoverage
from app.dataModel.spatial.grid.coordinateTypes import FineX, FineY, GridX
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionsSnapshot
from app.application.worldData.masks.regionRasterContext import RasterWorld


def invalid_region_extent(world: RasterWorld, snapshot: TerrainRegionsSnapshot, coverage: RegionCoverage) -> None:
    CoverageSpan(y=FineY(0), x0=GridX(0), x1=FineX(1))  # EXPECT: reportArgumentType
    RegionCoverageMeasure.union((coverage,))  # EXPECT: reportCallIssue
    prepare_terrain_regions(world, inputs=snapshot)  # EXPECT: reportArgumentType
    snapshot.world_uid = "other"  # EXPECT: reportAttributeAccessIssue


from app.dataModel.hydrology.declaredBasin import DeclaredBasin
from app.dataModel.hydrology.declaredLake import DeclaredLake
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, ProceduralSource
from app.dataModel.terrain.designedWater.fields.field import NoiseRecipe
from app.dataModel.terrain.designedWater.settings.plateGenerationPolicy import PlateGenerationPolicy
from app.dataModel.terrain.designedWater.settings.fieldCompositionPolicy import FieldCompositionPolicy
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile
from app.dataModel.spatial.grid.coordinateTypes import FineZ
from app.dataModel.topology.worldTopology import WorldTopology


def invalid_water_contracts(lake: DeclaredLake, basin: DeclaredBasin, topology: WorldTopology,
                            recipe: NoiseRecipe, profile: FieldFloorProfile) -> None:
    AuthoredBasinSource(value=lake)  # EXPECT: reportArgumentType
    ProceduralSource(value=basin)  # EXPECT: reportArgumentType
    NoiseRecipe(seed_root="world", topology=topology, noise_policy=PlateGenerationPolicy())  # EXPECT: reportArgumentType
    FieldCompositionPolicy(operator="add_clamp")  # EXPECT: reportArgumentType
    FieldFloorProfile(recipe=recipe, level=GridX(0), depth=10, z_min=FineZ(-20))  # EXPECT: reportArgumentType
    profile.z_min = FineZ(-30)  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.dataModel.hydrology.generation.generationContext import WaterGenerationContext, ResolvedWaterGenerationContext
from app.dataModel.terrain.designedWater.input import AuthoredWaterDesignInput, NoiseWaterDesignInput, PlateWaterDesignInput
from app.dataModel.terrain.designedWater.draft import AuthoredWaterDesignDraft, ProceduralWaterDesignDraft
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageAllocation, WaterCoverageBudget
from app.dataModel.terrain.designedWater.fields.field import PlateRecipe


def invalid_strategy_boundary(authored: AuthoredWaterDesignInput, noise: NoiseWaterDesignInput,
                               plate: PlateWaterDesignInput, runtime: WaterGenerationContext,
                               draft: ProceduralWaterDesignDraft, factory: DesignedWaterStrategyFactory) -> None:
    factory.get("plate")  # EXPECT: reportArgumentType
    wrong_recipe: NoiseRecipe = plate.field_policy  # EXPECT: reportAssignmentType
    wrong_recipe2: PlateRecipe = noise.field_policy  # EXPECT: reportAssignmentType
    wrong_context: ResolvedWaterGenerationContext = runtime  # EXPECT: reportAssignmentType
    wrong_budget: WaterCoverageBudget = noise.budget  # EXPECT: reportAssignmentType
    wrong_source: ProceduralSource = authored.source  # EXPECT: reportAssignmentType
    authored.field_policy  # EXPECT: reportAttributeAccessIssue
    draft.footprints  # EXPECT: reportAttributeAccessIssue
    wrong_input: NoiseWaterDesignInput = authored  # EXPECT: reportAssignmentType
    noise.seed_root = "changed"  # EXPECT: reportAttributeAccessIssue
    BodyCoverageAllocation(source_uid="source", generation_region_uid="region", requested_fine2=GridX(2), allocated_fine2=1.5)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.designedWater.coverage.waterCoverageBudgetPolicy import WaterCoverageBudgetPolicy
from app.dataModel.terrain.designedWater.coverage.budget import BodyCoverageRequest
from app.dataModel.terrain.regions.terrainRegionExtent import TerrainRegionExtent
from app.dataModel.spatial.grid.gridBBox import GridBBox


def invalid_budget_boundary(policy: WaterCoverageBudgetPolicy, extent: TerrainRegionExtent,
                            context: ResolvedWaterGenerationContext, runtime: WaterGenerationContext,
                            requests: tuple[BodyCoverageRequest, ...], bbox: GridBBox) -> None:
    policy.calculate(bbox, context, requests, authored_union_fine2=0, available_auto_area_fine2=1)  # EXPECT: reportArgumentType
    policy.calculate(extent, runtime, requests, authored_union_fine2=0, available_auto_area_fine2=1)  # EXPECT: reportArgumentType
    policy.calculate(extent, context, list(requests), authored_union_fine2=0, available_auto_area_fine2=1)  # EXPECT: reportArgumentType
    policy.calculate(extent, context, ({"source_uid": "a"},), authored_union_fine2=0, available_auto_area_fine2=1)  # EXPECT: reportArgumentType
    policy.calculate(extent, context, requests, authored_union_fine2=0.5, available_auto_area_fine2=1)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy
from app.dataModel.terrain.designedWater.settings.continentalNoisePolicy import ContinentalNoisePolicy
from app.dataModel.placement.prepared import PreparedPlacementV2


def invalid_geometry_boundary(preparer: DesignedWaterPlacementPreparer, input: NoiseWaterDesignInput,
                              draft: ProceduralWaterDesignDraft, selection: WaterFieldSelectionPolicy,
                              result: WaterDesignPreparation) -> None:
    preparer.prepare(input, draft)  # EXPECT: reportCallIssue
    preparer.prepare(input, draft, selection_policy=ContinentalNoisePolicy())  # EXPECT: reportArgumentType
    preparer.prepare(input, draft, selection_policy={"score_bits": 24})  # EXPECT: reportArgumentType
    preparer.prepare({"source": "source"}, draft, selection_policy=selection)  # EXPECT: reportArgumentType
    prepared: PreparedPlacementV2 = result  # EXPECT: reportAssignmentType
    result.decision  # EXPECT: reportAttributeAccessIssue
    result.original_area = 3.0  # EXPECT: reportAttributeAccessIssue
    input.field_policy.noise_policy.score_bits  # EXPECT: reportAttributeAccessIssue


from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry, AuthoredWaterGeometryRequest
from app.application.worldData.placement.adapters.water import prepare_authored_water_geometry
from app.application.worldData.placement.adapters.waterShape import shape_cells
from app.application.worldData.placement.adapters.waterTypes import WaterPlacementContext
from app.application.worldData.generators.hydrology.placement.projectDeclaredHydrology import project_water_source


def invalid_authored_boundary(request: AuthoredWaterGeometryRequest, geometry: AuthoredWaterGeometry,
                             context: WaterPlacementContext, basin: DeclaredBasin) -> None:
    prepare_authored_water_geometry({"source": "source"})  # EXPECT: reportArgumentType
    prepare_authored_water_geometry(geometry)  # EXPECT: reportArgumentType
    wrong_geometry: AuthoredWaterGeometry = request  # EXPECT: reportAssignmentType
    request.seed_root = "changed"  # EXPECT: reportAttributeAccessIssue
    geometry.rim_level = FineZ(0)  # EXPECT: reportAttributeAccessIssue
    shape_cells(basin.footprint, "source", context)  # EXPECT: reportCallIssue
    wrong_projection: DeclaredLake = project_water_source(basin, 2)  # EXPECT: reportAssignmentType


from app.dataModel.hydrology.declaredCoastline import CoastlinePurpose, DeclaredCoastline
from app.dataModel.hydrology.enums.basinKind import BasinKind


def invalid_coastline_purpose(value: DeclaredCoastline) -> None:
    DeclaredCoastline(location_uid="line", kind=BasinKind.SEA, purpose="water_source")  # EXPECT: reportArgumentType
    DeclaredCoastline(location_uid="line", kind=BasinKind.SEA, purpose=CoastlinePurpose.BODY_BOUNDARY, target_source_uid=1)  # EXPECT: reportArgumentType
    wrong_purpose: CoastlinePurpose = BasinKind.SEA  # EXPECT: reportAssignmentType
    value.is_water_source = True  # EXPECT: reportAttributeAccessIssue


from app.dataModel.terrain.designedWater.strategyKind import DesignedWaterStrategyKind
from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import HydrologyPlacementGateInputs, HydrologyPlacementBehaviorInputs, HydrologyPolicySnapshot
from app.application.worldData.generators.hydrology.policy.hydrologyPlacementBinding import bind_hydrology_placement_policy
from app.dataModel.hydrology.planning.sourceBodyMapping import SourceBodyMappingEntry
from app.dataModel.hydrology.seas import HydrologySeasPolicy


def invalid_water_policy_inputs(snapshot: HydrologyPolicySnapshot) -> None:
    HydrologyPlacementGateInputs(world_enabled=True)  # EXPECT: reportCallIssue
    HydrologyPlacementBehaviorInputs(strategy=BasinKind.SEA)  # EXPECT: reportArgumentType
    SourceBodyMappingEntry(source_uid="source", body_uids=["body"])  # EXPECT: reportArgumentType
    snapshot.world_uid = "other"  # EXPECT: reportAttributeAccessIssue
    bind_hydrology_placement_policy({}, HydrologySeasPolicy(), HydrologyPlacementGateInputs(world_enabled=True, category_enabled=True), HydrologyPlacementBehaviorInputs(strategy=DesignedWaterStrategyKind.PLATE), snapshot, source_path=(), category_path=())  # EXPECT: reportArgumentType


from app.dataModel.terrain.designedWater.input import WaterDesignInput, PlateNoiseWaterDesignInput
from app.dataModel.hydrology.sources.waterDesignSource import AuthoredBasinSource, CoastlineWaterSource


def invalid_generic_water_inputs(coast: NoiseWaterDesignInput[CoastlineWaterSource],
                                 procedural: NoiseWaterDesignInput[ProceduralSource]) -> None:
    bad_noise: NoiseWaterDesignInput[AuthoredBasinSource]  # EXPECT: reportInvalidTypeArguments
    bad_plate: PlateWaterDesignInput[AuthoredBasinSource]  # EXPECT: reportInvalidTypeArguments
    bad_mixed: PlateNoiseWaterDesignInput[AuthoredBasinSource]  # EXPECT: reportInvalidTypeArguments
    bad_authored: AuthoredWaterDesignInput[ProceduralSource]  # EXPECT: reportInvalidTypeArguments
    wrong_source: ProceduralSource = coast.source  # EXPECT: reportAssignmentType
    wrong_specialization: NoiseWaterDesignInput[ProceduralSource] = coast  # EXPECT: reportAssignmentType
    wrong_base: WaterDesignInput[CoastlineWaterSource] = procedural  # EXPECT: reportAssignmentType


from app.dataModel.terrain.designedWater.geometry.waterDesignConstraints import WaterDesignConstraints
from app.application.worldData.generators.terrain.designedWater.preparation.coastlineConstraintPreparer import CoastlineConstraintPreparer


from app.dataModel.topology.worldTopology import Coord


def invalid_coastline_constraints(value: WaterDesignConstraints, input: NoiseWaterDesignInput) -> None:
    CoastlineConstraintPreparer().prepare({})  # EXPECT: reportArgumentType
    CoastlineConstraintPreparer().prepare(input)  # EXPECT: reportArgumentType
    value.required_cells = frozenset()  # EXPECT: reportAttributeAccessIssue
    wrong_allowed: list[Coord] = value.allowed_cells  # EXPECT: reportAssignmentType
    wrong_constraints: WaterDesignConstraints = input.constraints  # EXPECT: reportAssignmentType


from app.application.worldData.generators.terrain.designedWater.preparation.coastlineWaterSourceAdapter import CoastlineWaterSourceAdapter
from app.dataModel.terrain.designedWater.input import CoastlineWaterDesignInput
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput


def invalid_coastline_source_join(input: CoastlineWaterDesignInput, generation: HydrologyGenerationDecision,
                                  admission: PlacementAdmissionInput) -> None:
    CoastlineWaterSourceAdapter().prepare_source(input.source.value)  # EXPECT: reportCallIssue
    wrong_source: ProceduralSource = input.source  # EXPECT: reportAssignmentType
    wrong_admission: PlacementAdmissionInput = generation  # EXPECT: reportAssignmentType
    wrong_generation: HydrologyGenerationDecision = admission.decision  # EXPECT: reportAssignmentType


from app.application.worldData.generators.hydrology.boundaries.boundaryGeometry import BoundaryGeometryResult
from app.application.worldData.generators.hydrology.boundaries.boundaryPlanner import CoastlineBoundaryPlanner
from app.application.worldData.placement.adapters.coastline.attachedCoastline import AttachedCoastlinePreparer, PreparedCoastlineBoundary
from app.dataModel.hydrology.boundaries.attachedCoastline import AttachedCoastline, CoastlineBoundaryInput, CoastlinePart
from app.dataModel.hydrology.boundaries.boundaryWaterSnapshot import BoundaryWaterSnapshot, FineBoundaryWaterCell
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint


def invalid_attached_boundary(source: DeclaredCoastline, snapshot: BoundaryWaterSnapshot,
                              admission: PlacementAdmissionInput, input: CoastlineBoundaryInput,
                              result: BoundaryGeometryResult, prepared: PreparedCoastlineBoundary) -> None:
    AttachedCoastlinePreparer().prepare_boundary({}, snapshot, admission)  # EXPECT: reportArgumentType
    FineBoundaryWaterCell(cell=SurfaceGridCoord(GridX(0), GridY(0)), body_uid=None)  # EXPECT: reportArgumentType
    wrong_cell: SurfaceGridCoord = snapshot.fine_cells[0].cell  # EXPECT: reportAssignmentType
    wrong_boundary: AttachedCoastline = prepared.prepared  # EXPECT: reportAssignmentType
    wrong_prepared: PreparedPlacementV2 = result.boundary  # EXPECT: reportAssignmentType
    CoastlineBoundaryPlanner().prepare(input, snapshot, [admission], snapshot_uid="dependent")  # EXPECT: reportArgumentType
    CoastlinePart(body_uid="physical", closed=False, path=[HydrologyWaypoint(x=0,y=0)])  # EXPECT: reportArgumentType
    snapshot.fine_cells = ()  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.generators.terrain.designedWater.fields.noiseFieldGenerator import NoiseFieldGenerator
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.continentalNoiseStrategy import ContinentalNoiseStrategy


def invalid_continental_noise(noise: NoiseWaterDesignInput, plate: PlateWaterDesignInput) -> None:
    NoiseFieldGenerator().build(plate)  # EXPECT: reportArgumentType
    NoiseFieldGenerator().sample(plate.field_policy,x=0.5,y=0.5)  # EXPECT: reportArgumentType
    ContinentalNoiseStrategy().design({})  # EXPECT: reportArgumentType
    wrong_z: GridX = noise.z_min  # EXPECT: reportAssignmentType
    noise.z_min = FineZ(-10)  # EXPECT: reportAttributeAccessIssue
    NoiseFieldGenerator().build(noise).budget  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.generators.terrain.designedWater.fields.plateFieldGenerator import PlateFieldGenerator
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateStrategy import PlateStrategy
from app.dataModel.terrain.designedWater.fields.plateLayout import PlateLayout


def invalid_plate_field(noise: NoiseWaterDesignInput, plate: PlateWaterDesignInput, layout: PlateLayout) -> None:
    PlateFieldGenerator().build(noise)  # EXPECT: reportArgumentType
    PlateFieldGenerator().sample(plate.field_policy,x=0.5,y=0.5)  # EXPECT: reportArgumentType
    PlateStrategy().design({})  # EXPECT: reportArgumentType
    layout.effective_count = 1  # EXPECT: reportAttributeAccessIssue
    layout.centers[0].buoyancy = 0.0  # EXPECT: reportAttributeAccessIssue
    wrong_recipe: NoiseRecipe = layout.recipe  # EXPECT: reportAssignmentType
    PlateFieldGenerator().build(plate).original_area  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.generators.terrain.designedWater.fields.continentalFieldComposer import ContinentalFieldComposer
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.plateNoiseStrategy import PlateNoiseStrategy


from app.dataModel.terrain.designedWater.fields.field import ContinentalField


def invalid_composition(mixed: PlateNoiseWaterDesignInput, plate: PlateWaterDesignInput, field: ContinentalField, layout: PlateLayout) -> None:
    ContinentalFieldComposer().combine(field, field, plate.field_policy)  # EXPECT: reportArgumentType
    ContinentalFieldComposer().combine({}, field, mixed.field_policy)  # EXPECT: reportArgumentType
    ContinentalFieldComposer().sample(mixed.field_policy, field, x=.5, y=.5)  # EXPECT: reportArgumentType
    PlateNoiseStrategy().design({})  # EXPECT: reportArgumentType
    PlateFieldGenerator().layout(mixed.field_policy)  # EXPECT: reportArgumentType
    NoiseFieldGenerator().sample(mixed.field_policy, x=.5, y=.5)  # EXPECT: reportArgumentType
    mixed.field_policy.plate_recipe = plate.field_policy  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.placement.adapters.waterTypes import PreparedWaterEntry
from app.dataModel.placement import PreparedPlacement


def invalid_metadata_transport(entry: PreparedWaterEntry, prepared: PreparedPlacement) -> None:
    entry.source.location_uid  # EXPECT: reportAttributeAccessIssue
    entry.kind  # EXPECT: reportAttributeAccessIssue
    PreparedWaterEntry(source={}, prepared=prepared, floor_z=FineZ(-5), floor_profile=None)  # EXPECT: reportArgumentType
    PreparedWaterEntry(source=entry.source, prepared=prepared, floor_z=FineZ(-5), floor_profile={})  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.reliefObjects.bathymetry.floorProfile import BasinFloorEvaluator
from app.dataModel.terrain.relief.bathymetry.floorProfile import FieldFloorProfile


from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace


def invalid_basin_floor(input: NoiseWaterDesignInput, profile: FieldFloorProfile) -> None:
    BasinFloorEvaluator({}, topology=input.topology, coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID, grid=input.grid)  # EXPECT: reportArgumentType
    BasinFloorEvaluator(profile, topology=input.topology, coordinate_space="world_surface_grid", grid=input.grid)  # EXPECT: reportArgumentType
    BasinFloorEvaluator(profile, topology=input.topology, coordinate_space=CoordinateSpace.WORLD_SURFACE_GRID, grid={})  # EXPECT: reportArgumentType
    BasinFloorEvaluator(profile, topology=input.topology, coordinate_space=CoordinateSpace.WORLD_FINE_GRID, grid=None).sample((0.5, 1))  # EXPECT: reportArgumentType


from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import SurfaceSupportInput, MaterialSupportEntry
from app.dataModel.materials.enums.materialCategory import MaterialCategory


def invalid_support_sources(value: SurfaceSupportInput) -> None:
    MaterialSupportEntry(key=value.materials[0].key, category=MaterialCategory.SOLID, substrate="rock")  # EXPECT: reportArgumentType
    value.templates[0][1].conditions.append(None)  # EXPECT: reportAttributeAccessIssue
    value.templates[0][1].structure_refs.append("ref")  # EXPECT: reportAttributeAccessIssue
    value.materials = ()  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.generators.terrain.relief.surfaceCoatingSupport import SurfaceCoatingSupportProvider, SurfaceSupportDependencies, CoatingPlanProvider
from app.dataModel.terrain.relief.surfaceCoating.surfaceCoatingFacts import SurfaceSupportPlan
from app.dataModel.terrain.relief.surfaceCoating.surfaceSupportInput import CoatingPlanInput
from app.dataModel.terrain.regions.coverageGeometry import RegionCoverage


def invalid_coating(request: PlanRequest[SurfaceSupportInput], dependencies: SurfaceSupportDependencies,
                    cells: RegionCoverage, inputs: CoatingPlanInput, support: SurfaceSupportPlan) -> None:
    SurfaceCoatingSupportProvider.facts(request, {}, cells=cells)  # EXPECT: reportArgumentType
    SurfaceCoatingSupportProvider.facts(request, dependencies, cells=())  # EXPECT: reportArgumentType
    CoatingPlanProvider.plan(inputs, support, dependencies.relief.payload, fine_span=2)  # EXPECT: reportArgumentType
    support.facts[0].face = "north"  # EXPECT: reportAttributeAccessIssue


from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyPlan


def invalid_geo_climate_handle(provider: ClimateLocalPlanProvider[GeoHydrologyPlan]) -> ClimateLocalPlanProvider[HydrologyPlan]:
    return provider  # EXPECT: reportReturnType


def invalid_geo_support_handle(provider: SurfaceCoatingSupportProvider[GeoHydrologyPlan]) -> SurfaceCoatingSupportProvider[HydrologyPlan]:
    return provider  # EXPECT: reportReturnType


def invalid_geo_coating_handle(provider: CoatingPlanProvider[GeoHydrologyPlan]) -> CoatingPlanProvider[HydrologyPlan]:
    return provider  # EXPECT: reportReturnType


def invalid_geo_support_dependencies(deps: SurfaceSupportDependencies[GeoHydrologyPlan]) -> SurfaceSupportDependencies[HydrologyPlan]:
    return deps  # EXPECT: reportReturnType


def invalid_geo_fields_in_common_kernel(hydrology: HydrologyPlan) -> None:
    hydrology.source_mapping  # EXPECT: reportAttributeAccessIssue
    hydrology.classification_decisions  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.planning.contracts.surfacePlanBundle import GeoSurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import GeoSurfacePlanningView
from app.dataModel.hydrology.planning.hydrologyPlan import GeoHydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.geoHydrologyPlanInput import GeoHydrologyPlanInput
from app.dataModel.terrain.planning.inputs.geoWaterPlacementInput import GeoWaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import GeoWaterPlacementPlan


def invalid_pc_geo_inputs(water: WaterPlacementInput, routes: HydrologyPlanInput) -> tuple[GeoWaterPlacementInput, GeoHydrologyPlanInput]:
    return water, routes  # EXPECT: reportReturnType


def invalid_pc_geo_envelopes(geo: GeoSurfacePlanBundle) -> tuple[PlanEnvelope[WaterPlacementPlan], PlanEnvelope[HydrologyRoutesPlan]]:
    return geo.water_placement, geo.hydrology_routes  # EXPECT: reportReturnType


def invalid_geo_phase_substitution(geo: GeoSurfacePlanBundle) -> PlanEnvelope[GeoHydrologyRoutesPlan]:
    return geo.hydrology  # EXPECT: reportReturnType


def invalid_geo_capture(view: GeoSurfacePlanningView) -> None:
    view.hydrology.classification_decisions  # EXPECT: reportAttributeAccessIssue
    view.water_placement.source_decisions  # EXPECT: reportAttributeAccessIssue


def invalid_geo_envelope_widening(value: PlanEnvelope[GeoWaterPlacementPlan]) -> PlanEnvelope[WaterPlacementPlan]:
    return value  # EXPECT: reportReturnType


def invalid_geo_boundary_snapshot(value: BoundaryWaterSnapshot[GeoHydrologyPlan]) -> BoundaryWaterSnapshot[HydrologyPlan]:
    return value  # EXPECT: reportReturnType


def invalid_pc_boundary_snapshot(value: BoundaryWaterSnapshot[HydrologyPlan]) -> BoundaryWaterSnapshot[GeoHydrologyPlan]:
    return value  # EXPECT: reportReturnType


def invalid_geo_policy_snapshot(value: HydrologyPolicySnapshot[GeoHydrologyPlan]) -> HydrologyPolicySnapshot[HydrologyPlan]:
    return value  # EXPECT: reportReturnType


def invalid_pc_policy_snapshot(value: HydrologyPolicySnapshot[HydrologyPlan]) -> HydrologyPolicySnapshot[GeoHydrologyPlan]:
    return value  # EXPECT: reportReturnType


from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import GeoHydrologyFinalPlanProvider


def invalid_geo_final_provider_request(provider: GeoHydrologyFinalPlanProvider, request: PlanRequest[HydrologyPlanInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> None:
    provider.build(request, dependencies, control)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import GeoReliefPlanProvider, GeoRiverReliefPlanProvider


def invalid_pc_geo_relief_handles(base: RegisteredPlanContract[ClimateBaseInput, ClimateBasePlan],
    terrain: RegisteredPlanContract[TerrainBaseInput, TerrainPlan],
    water_pc: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan],
    water_geo: RegisteredPlanContract[GeoWaterPlacementInput, GeoWaterPlacementPlan],
    relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
    routes_pc: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan],
    routes_geo: RegisteredPlanContract[GeoHydrologyPlanInput, GeoHydrologyRoutesPlan]) -> None:
    GeoReliefPlanProvider(base, terrain, water_pc)  # EXPECT: reportArgumentType
    GeoRiverReliefPlanProvider(relief, routes_pc)  # EXPECT: reportArgumentType
    ReliefPlanProvider(base, terrain, water_geo)  # EXPECT: reportArgumentType
    RiverReliefPlanProvider(relief, routes_geo)  # EXPECT: reportArgumentType


from app.application.worldData.generators.hydrology.water.waterMaterialize import MaterializedWater


def invalid_materialized_source_mapping(result: MaterializedWater) -> dict[str, tuple[str, ...]]:
    return result.source_mapping  # EXPECT: reportReturnType


from app.dataModel.hydrology.generation.waterGenerationSettings import BodyWaterGenerationSettings


def invalid_route_root_generation(value: GeoHydrologyPlanInput) -> BodyWaterGenerationSettings:
    return value.generation  # EXPECT: reportReturnType


from app.application.worldData.generators.hydrology.policy.hydrologyGenerationBinding import bind_hydrology_generation_policy
from app.dataModel.hydrology.generation.waterGenerationSettings import CategoryWaterGenerationSettings


def invalid_generation_binding_sources(inputs: GeoHydrologyPlanInput, category: CategoryWaterGenerationSettings,
    body: BodyWaterGenerationSettings) -> None:
    bind_hydrology_generation_policy(enabled=inputs.enabled, generation=body, defaults=inputs.defaults, category=category, root_path=(), context_path=())  # EXPECT: reportArgumentType
    bind_hydrology_generation_policy(enabled=inputs.enabled, generation=inputs.generation, defaults=inputs.defaults, category=body, root_path=(), context_path=())  # EXPECT: reportArgumentType
    bind_hydrology_generation_policy(enabled=inputs.enabled, generation=inputs.generation, defaults=inputs.defaults, category=category, body=category, root_path=(), context_path=())  # EXPECT: reportArgumentType


from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.dataModel.hydrology.enums.planning.waterGenerationScope import WaterGenerationCategory
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import WaterDesignDecision


def invalid_geo_fill_decisions(owner: WaterBodyPlanner, inputs: GeoHydrologyPlanInput, placement: GeoWaterPlacementPlan,
    admission: tuple[tuple[WaterGenerationCategory, WaterDesignDecision], ...], control: PlanBuildControl) -> None:
    owner.plan_geo(world_uid="world", inputs=inputs, placement=placement, surface_z=(), classification_decisions=admission, control=control)  # EXPECT: reportArgumentType


from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.dataModel.hydrology.policy.hydrologyGenerationDecision import HydrologyGenerationDecision


def invalid_geo_route_placement(owner: HydrologyRoutesAssembler, inputs: GeoHydrologyPlanInput,
    relief: ReliefPlan, placement: WaterPlacementPlan,
    decisions: tuple[tuple[WaterGenerationCategory, HydrologyGenerationDecision], ...], control: PlanBuildControl) -> None:
    owner.assemble_geo(world_uid="world", inputs=inputs, relief=relief, placement=placement, classification_decisions=decisions, control=control)  # EXPECT: reportArgumentType



def invalid_captured_category_source(inputs: GeoHydrologyPlanInput) -> BodyWaterGenerationSettings:
    return inputs.lake_generation  # EXPECT: reportReturnType


from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import GeoHydrologyRoutesPlanProvider
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.policy.policyResolver import PolicyResolver


def invalid_geo_routes_provider_request(provider: GeoHydrologyRoutesPlanProvider, request: PlanRequest[HydrologyPlanInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> None:
    provider.build(request, dependencies, control)  # EXPECT: reportArgumentType


def invalid_geo_routes_water_handle(relief: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
    water: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan], assembler: HydrologyRoutesAssembler,
    policy: PolicyResolver) -> None:
    GeoHydrologyRoutesPlanProvider(relief, water, assembler, policy)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.regions.regionExtent import TerrainRegionPlanProvider


def invalid_region_provider_request(provider: TerrainRegionPlanProvider, request: PlanRequest[GeoWaterPlacementInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> None:
    provider.build(request, dependencies, control)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.designedWater.preparation.proceduralWaterSourceAdapter import ProceduralWaterSourceAdapter
from app.dataModel.terrain.designedWater.input import WaterDesignInput
from app.dataModel.hydrology.sources.waterDesignSource import CoastlineWaterSource
from app.dataModel.terrain.designedWater.fields.field import WaterFieldRecipe


def invalid_procedural_source_join(adapter: ProceduralWaterSourceAdapter, shared: WaterDesignInput[CoastlineWaterSource],
    generation: HydrologyGenerationDecision, admission: PlacementAdmissionInput, recipe: WaterFieldRecipe, z_min: FineZ) -> None:
    adapter.prepare_source(shared, generation=generation, admission=admission, field_policy=recipe, z_min=z_min)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.designedWater.preparation.authoredWaterSourceAdapter import AuthoredWaterSourceAdapter
from app.dataModel.terrain.designedWater.geometry.authoredGeometry import AuthoredWaterGeometry


def invalid_authored_source_join(adapter: AuthoredWaterSourceAdapter, shared: WaterDesignInput[CoastlineWaterSource],
    generation: HydrologyGenerationDecision, admission: PlacementAdmissionInput, geometry: AuthoredWaterGeometry) -> None:
    adapter.prepare_source(shared, generation=generation, admission=admission, geometry=geometry)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.designedWater.preparation.placementPreparation import DesignedWaterPlacementPreparer
from app.dataModel.terrain.designedWater.preparation.result import WaterDesignPreparation
from app.dataModel.terrain.designedWater.input import WaterStrategyInput
from app.dataModel.placement.lifecycle.header import PlacementHeader


def invalid_prepared_water_intent(owner: DesignedWaterPlacementPreparer, value: WaterStrategyInput,
    preparation: WaterDesignPreparation, header: PlacementHeader, admission: PlacementAdmissionInput) -> None:
    owner.bind_admission(value, preparation, intent=header, admission=admission)  # EXPECT: reportArgumentType


from collections.abc import Callable
from app.application.worldData.placement.lifecycle.session import PlacementSession


def invalid_placement_runner_callback(session: PlacementSession, prepare: Callable[[PlacementHeader], None]) -> None:
    session.run(prepare)  # EXPECT: reportArgumentType


from app.application.worldData.planning.composition.planProviders import GeoWorldPlanProviders, WorldPlanProviders
from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningView
from app.application.planning.service.planningService import PlanWaitControl


def invalid_assembler_family(pc: SurfacePlanningAssembler[WorldPlanProviders], geo: SurfacePlanningAssembler[GeoWorldPlanProviders],
    pc_view: SurfacePlanningView, geo_view: GeoSurfacePlanningView, wait: PlanWaitControl) -> None:
    pc.prepare_geo(geo_view, wait=wait)  # EXPECT: reportAttributeAccessIssue
    geo.prepare(pc_view, wait=wait)  # EXPECT: reportAttributeAccessIssue


from app.application.worldData.planning.composition.surfacePlanningAssembler import prepare_captured_geo_bundle
from app.application.jsonValidation.resolve import ResolveContext


def invalid_geo_reporting_family(pc: SurfacePlanningAssembler[WorldPlanProviders], view: GeoSurfacePlanningView,
    wait: PlanWaitControl, ctx: ResolveContext) -> None:
    prepare_captured_geo_bundle(view, planning=pc, wait=wait, resolve_ctx=ctx)  # EXPECT: reportArgumentType


from app.application.worldData.generators.terrain.designedWater.preparation.designPreparation import prepare_designed_water
from app.application.worldData.generators.terrain.designedWater.strategies.strategyFactory import DesignedWaterStrategyFactory
from app.application.planning.service.planningService import PlanBuildControl
from app.dataModel.terrain.designedWater.input import WaterStrategyInput
from app.dataModel.placement.batch import PlacementBatchV2
from app.dataModel.placement.lifecycle.admission import PlacementAdmissionInput
from app.dataModel.placement.prepared import PreparedPlacementV2
from app.dataModel.spatial.grid.gridSettings import SurfaceGridSettings
from app.dataModel.terrain.designedWater.settings.fieldSelectionPolicy import WaterFieldSelectionPolicy


from app.dataModel.hydrology.generation.generationContext import ResolvedWaterGenerationContext
from app.dataModel.terrain.designedWater.coverage.budget import WaterCoverageBudget
from app.dataModel.terrain.regions.terrainRegionsSnapshot import TerrainRegionPlan


def invalid_water_universe_callback(batch: PlacementBatchV2, terrain: PlanEnvelope[TerrainPlan],
    grid: SurfaceGridSettings, control: PlanBuildControl,
    prepare: Callable[[PlacementAdmissionInput, WaterCoverageBudget | None], WaterDesignPreparation],
    competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2],
    regions: TerrainRegionPlan, world_context: ResolvedWaterGenerationContext) -> None:
    prepare_designed_water(batch, water_intents=(), pre_hydrology=terrain, grid=grid, seed_root="seed",
        prepare_input=prepare, prepare_competitor=competitor,  # EXPECT: reportArgumentType
        regions=regions, world_context=world_context, coverage_requests=(),
        authored_geometry=(),
        strategies=DesignedWaterStrategyFactory.builtins(), selection_policy=WaterFieldSelectionPolicy(), control=control)


def invalid_water_budget_callback(batch: PlacementBatchV2, terrain: PlanEnvelope[TerrainPlan],
    grid: SurfaceGridSettings, control: PlanBuildControl,
    prepare: Callable[[PlacementAdmissionInput], WaterStrategyInput],
    competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2], regions: TerrainRegionPlan,
    world_context: ResolvedWaterGenerationContext, budget: WaterCoverageBudget) -> None:
    prepare_designed_water(batch, water_intents=(), pre_hydrology=terrain, grid=grid, seed_root="seed",
        prepare_input=prepare, prepare_competitor=competitor,  # EXPECT: reportArgumentType
        regions=regions, world_context=world_context, coverage_requests=(),
        authored_geometry=(),
        strategies=DesignedWaterStrategyFactory.builtins(), selection_policy=WaterFieldSelectionPolicy(), control=control)
    prepare_designed_water(batch, water_intents=(), pre_hydrology=terrain, grid=grid, seed_root="seed",
        prepare_input=lambda admission, allocation: prepare(admission), prepare_competitor=competitor,
        regions=regions, world_context=world_context, coverage_requests=(budget,),  # EXPECT: reportArgumentType
        authored_geometry=(),
        strategies=DesignedWaterStrategyFactory.builtins(), selection_policy=WaterFieldSelectionPolicy(), control=control)
    prepare_designed_water(batch, water_intents=(), pre_hydrology=terrain, grid=grid, seed_root="seed",
        prepare_input=lambda admission, allocation: prepare(admission), prepare_competitor=competitor,
        regions=regions, world_context=world_context, coverage_requests=(),
        authored_geometry=(budget,),  # EXPECT: reportArgumentType
        strategies=DesignedWaterStrategyFactory.builtins(), selection_policy=WaterFieldSelectionPolicy(), control=control)


from app.application.worldData.generators.terrain.designedWater.preparation.proceduralDesignPreparation import prepare_procedural_designed_water


def invalid_native_source_producer(legacy: WaterPlacementInput, batch: PlacementBatchV2,
    terrain: PlanEnvelope[TerrainPlan], regions: TerrainRegionPlan,
    competitor: Callable[[PlacementAdmissionInput], PreparedPlacementV2], control: PlanBuildControl,
    source: ProceduralSource, snapshot: HydrologyPolicySnapshot, decision: WaterDesignDecision) -> None:
    prepare_procedural_designed_water(legacy, batch, water_intents=(),  # EXPECT: reportArgumentType
        pre_hydrology=terrain, regions=regions, seed_root="seed", prepare_competitor=competitor,
        strategies=DesignedWaterStrategyFactory.builtins(), control=control)
    bind_hydrology_placement_policy(source, HydrologySeasPolicy(),
        HydrologyPlacementGateInputs(world_enabled=True, category_enabled=True),
        HydrologyPlacementBehaviorInputs(strategy=DesignedWaterStrategyKind.PLATE), snapshot,
        source_path=(), category_path=(), generation=decision)  # EXPECT: reportArgumentType


from app.dataModel.hydrology.policy.hydrologyPlacementPolicy import HydrologyProceduralExtentFacts
from app.application.worldData.generators.terrain.designedWater.strategies.procedural.fieldRecipeFactory import WaterFieldRecipeFactory


def invalid_domain_preparation_contracts(inputs: GeoWaterPlacementInput) -> None:
    HydrologyProceduralExtentFacts(world_extent=True)  # EXPECT: reportArgumentType
    WaterFieldRecipeFactory().build("plate", inputs, "seed")  # EXPECT: reportArgumentType
