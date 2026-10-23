"""Every marked line must produce its specified pyright diagnostic."""

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
from tests.typing.planning.valid import (
    ClimateInput, ClimatePayload, HydroInput, HydroPayload, build_climate, require_climate, require_grid_x,
)


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
