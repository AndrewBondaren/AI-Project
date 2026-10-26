"""Typed contracts preserve I/T, nominal units and covariant diagnostic context."""

from app.application.worldData.planning.contracts.surfaceWorkingMaps import SurfaceWorkingMaps
from dataclasses import dataclass
from enum import StrEnum
from typing import assert_type

from app.application.cache.contracts.cacheBackend import CacheBackend, CacheBinding
from app.application.cache.backends.memoryCache import MemoryCache
from app.application.planning.providers.planProvider import PlanProvider, RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planningService import PlanningService, PlanWaitControl
from app.application.encoding.canonicalCodec import decode
from app.application.worldData.generators.climate.planning.climatePlanProvider import ClimateBasePlanProvider
from app.application.worldData.generators.terrain.planning.terrainPlanProvider import TerrainPlanProvider
from app.application.worldData.generators.terrain.planning.waterPlacementPlanProvider import WaterPlacementPlanProvider
from app.application.worldData.generators.terrain.relief.planning.reliefPlanProvider import ReliefPlanProvider, RiverReliefPlanProvider
from app.dataModel.terrain.relief.planning.inputs.reliefPlanInput import ReliefPlanInput, RiverReliefInput
from app.dataModel.terrain.planning.inputs.waterPlacementInput import WaterPlacementInput
from app.dataModel.terrain.planning.waterPlacementPlan import WaterPlacementPlan
from app.application.worldData.generators.climate.planning.climatePlanSampler import ClimatePlanSampler
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.application.cache.service.cacheService import CacheService
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission

from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.surfacePlanning.surfacePlanSlot import SurfacePlanSlot
from app.dataModel.spatial.grid.coordinateTypes import GridX
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverReliefPlan, RiverBedRecord
from app.dataModel.spatial.grid.coordinateTypes import SurfaceGridCoord
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyPlan, RiverRoute
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyPlanInput


@dataclass(frozen=True)
class ClimateInput:
    weights: tuple[int, ...]


@dataclass(frozen=True)
class HydroInput:
    level: int


@dataclass(frozen=True)
class ClimatePayload:
    temperatures: tuple[int, ...]


@dataclass(frozen=True)
class HydroPayload:
    depths: tuple[int, ...]


def cache_service_types(service: CacheService, backend: CacheBackend,
                        binding: CacheBinding[ClimatePayload],
                        key: CacheKey[ClimatePayload], entry: CacheEntry[ClimatePayload]) -> None:
    assert_type(service.get(binding, key), CacheLookup[ClimatePayload])
    assert_type(service.put(binding, entry), CacheAdmission)
    assert_type(service.evict(binding, key), None)
    assert_type(backend.get(key), CacheLookup[ClimatePayload])
    assert_type(backend.put(entry), None)


def memory_backend_protocol(backend: MemoryCache) -> CacheBackend:
    return backend


def canonical_decode_type(encoded: bytes, manifest: CanonicalSchemaManifest) -> ClimatePayload:
    return decode(encoded, ClimatePayload, manifest)


def climate_base_provider_type(provider: ClimateBasePlanProvider) -> PlanProvider[ClimateBaseInput, ClimateBasePlan]:
    return provider


def terrain_base_provider_type(provider: TerrainPlanProvider) -> PlanProvider[TerrainBaseInput, TerrainPlan]:
    return provider


def surface_slot_boundary(member: SurfacePlanSlot) -> PlanSlot:
    slot = PlanSlot(member.value)
    assert_type(slot, PlanSlot)
    return slot


def water_placement_provider_type(provider: WaterPlacementPlanProvider) -> PlanProvider[WaterPlacementInput, WaterPlacementPlan]:
    return provider


def relief_provider_type(provider: ReliefPlanProvider) -> PlanProvider[ReliefPlanInput, ReliefPlan]:
    return provider


def river_relief_provider_type(provider: RiverReliefPlanProvider) -> PlanProvider[RiverReliefInput, RiverReliefPlan]:
    return provider


def planning_service_types(service: PlanningService, registry: PlanRegistry,
                            contract: RegisteredPlanContract[ClimateInput, ClimatePayload],
                            provider: PlanProvider[ClimateInput, ClimatePayload],
                            request: PlanRequest[ClimateInput], reader: PlanDependencyReader,
                            wait: PlanWaitControl) -> PlanEnvelope[ClimatePayload]:
    registry.register(contract, provider)
    assert_type(reader.require(PlanSlot("base"), contract), PlanEnvelope[ClimatePayload])
    return service.get_or_build(contract, request, reader, wait=wait)


def cache_round_trip(key: CacheKey[PlanEnvelope[ClimatePayload]],
                     envelope: PlanEnvelope[ClimatePayload]) -> CacheEntry[PlanEnvelope[ClimatePayload]]:
    entry = CacheEntry[PlanEnvelope[ClimatePayload]](key=key, value=envelope)
    assert_type(entry.value.payload, ClimatePayload)
    return entry


def lookup_values(lookup: CacheLookup[PlanEnvelope[ClimatePayload]]) -> tuple[int, ...] | None:
    if isinstance(lookup, CacheHit):
        assert_type(lookup.entry.value.payload, ClimatePayload)
        return lookup.entry.value.payload.temperatures
    return None


def build_climate(request: PlanRequest[ClimateInput]) -> tuple[int, ...]:
    assert_type(request.inputs, ClimateInput)
    return request.inputs.weights


def require_climate(envelope: PlanEnvelope[ClimatePayload]) -> ClimatePayload:
    return envelope.payload


def require_grid_x(value: GridX) -> GridX:
    return value


class Action(StrEnum):
    DISABLE = "disable"


class Reason(StrEnum):
    INVALID = "invalid"


def widen_context(value: RuntimeIssueContext[Action, Reason]) -> RuntimeIssueContext[StrEnum, StrEnum]:
    return value


def climate_domain_round_trip(request: PlanRequest[ClimateBaseInput],
                              lookup: CacheLookup[PlanEnvelope[ClimateBasePlan]]) -> int | None:
    assert_type(request.inputs, ClimateBaseInput)
    if isinstance(lookup, CacheHit):
        assert_type(lookup.entry.value.payload, ClimateBasePlan)
        return lookup.entry.value.payload.profiles[0].values.base_temperature
    return None


def terrain_domain_round_trip(request: PlanRequest[TerrainBaseInput],
                              entry: CacheEntry[PlanEnvelope[TerrainPlan]]) -> TerrainPlan:
    assert_type(request.inputs, TerrainBaseInput)
    assert_type(entry.value.payload, TerrainPlan)
    return entry.value.payload


def relief_domain(entry: CacheEntry[PlanEnvelope[ReliefPlan]],
                  bed: RiverBedRecord[SurfaceGridCoord]) -> ReliefPlan:
    assert_type(bed.bed_z[0][0], SurfaceGridCoord)
    assert_type(entry.value.payload, ReliefPlan)
    return entry.value.payload


def hydrology_domain(request: PlanRequest[HydrologyPlanInput],
                     entry: CacheEntry[PlanEnvelope[HydrologyPlan]],
                     route: RiverRoute[SurfaceGridCoord]) -> HydrologyPlan:
    assert_type(request.inputs, HydrologyPlanInput)
    assert_type(route.receiver_cell, SurfaceGridCoord)
    assert_type(entry.value.payload, HydrologyPlan)
    return entry.value.payload


from app.application.worldData.generators.hydrology.planning.hydrologyPlanProvider import HydrologyRoutesPlanProvider, HydrologyFinalPlanProvider
from app.dataModel.hydrology.planning.hydrologyPlan import HydrologyRoutesPlan
from app.dataModel.hydrology.planning.inputs.hydrologyPlanInput import HydrologyFinalInput
from app.application.planning.service.planningService import PlanBuildControl
from app.application.planning.providers.planRegistry import PlanDependencyReader
from app.dataModel.planning.contracts.planEnvelope import PlanBuildResult


def hydrology_providers(routes: HydrologyRoutesPlanProvider, final: HydrologyFinalPlanProvider,
    route_request: PlanRequest[HydrologyPlanInput], final_request: PlanRequest[HydrologyFinalInput],
    reader: PlanDependencyReader, control: PlanBuildControl) -> None:
    assert_type(routes.build(route_request, reader, control), PlanBuildResult[HydrologyRoutesPlan])
    assert_type(final.build(final_request, reader, control), PlanBuildResult[HydrologyPlan])


from app.dataModel.hydrology.planning.stages.openWaterPlan import OpenWaterPlan
from app.dataModel.hydrology.planning.stages.riverRoutePlans import CoarseRiverPlan, FineRiverPlan, RiverRouteBatch
from app.dataModel.spatial.grid.coordinateTypes import FineXY


def intermediate_hydrology_plans(water: PlanBuildResult[OpenWaterPlan], coarse: CoarseRiverPlan,
    fine_batch: RiverRouteBatch[FineXY], fine: FineRiverPlan) -> None:
    assert_type(water.payload, OpenWaterPlan)
    assert_type(coarse, RiverRouteBatch[SurfaceGridCoord])
    assert_type(coarse.routes[0].receiver_cell, SurfaceGridCoord)
    assert_type(coarse.claims[0][0], SurfaceGridCoord)
    assert_type(fine_batch.routes[0].receiver_cell, FineXY)
    assert_type(fine_batch.claims[0][0], FineXY)
    assert_type(fine.base_surface_z[0][0], FineXY)


from app.application.worldData.generators.hydrology.water.planning.waterBodyPlanner import WaterBodyPlanner
from app.application.worldData.generators.hydrology.load.paint.declaredWaterPaintProjector import DeclaredWaterPaintProjector
from app.dataModel.hydrology.planning.hydrologyPlan import DeclaredWaterPaint
from app.dataModel.spatial.grid.coordinateTypes import FineZ


def hydrology_water_and_paint_owners(water: WaterBodyPlanner, paint: DeclaredWaterPaintProjector,
    inputs: HydrologyPlanInput, surface: tuple[tuple[SurfaceGridCoord, FineZ], ...],
    placement: WaterPlacementPlan, control: PlanBuildControl) -> None:
    assert_type(water.plan(world_uid="world", inputs=inputs, surface_z=surface,
        placement=placement, control=control), PlanBuildResult[OpenWaterPlan])
    assert_type(paint.project(rivers=inputs.declared_rivers, coastlines=inputs.coastlines,
        lakes=inputs.declared_lakes, anchors=inputs.anchors), PlanBuildResult[DeclaredWaterPaint])


from app.application.worldData.generators.hydrology.rivers.planning.coarseRiverPlanner import CoarseRiverPlanner
from app.application.worldData.generators.hydrology.rivers.planning.fineRiverPlanner import FineRiverPlanner
from app.application.worldData.generators.hydrology.rivers.riverPrepare import plan_prepared_routes
from app.application.worldData.generators.hydrology.rivers.riverRouteRequests import RiverRouteRequest
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from app.dataModel.spatial.grid.coordinateSpace import CoordinateSpace
from app.dataModel.spatial.grid.coordinateTypes import GridY
from app.dataModel.topology.worldTopology import Coord


def river_owners(coarse: CoarseRiverPlanner, fine: FineRiverPlanner, inputs: HydrologyPlanInput,
    surface: tuple[tuple[SurfaceGridCoord, FineZ], ...], water: OpenWaterPlan, control: PlanBuildControl) -> None:
    first = coarse.plan(world_uid="world", inputs=inputs, surface_z=surface, water=water, control=control)
    assert_type(first, PlanBuildResult[CoarseRiverPlan])
    assert_type(fine.plan(world_uid="world", inputs=inputs, surface_z=surface, water=water,
        coarse=first.payload, control=control), PlanBuildResult[FineRiverPlan])


def route_only_coarse_contract(inputs: HydrologyPlanInput, hm: SurfaceHeightmap,
    requests: tuple[RiverRouteRequest, ...], claims: dict[Coord, MapCellHydrology],
    control: PlanBuildControl) -> None:
    result = plan_prepared_routes(world_uid="world", span=inputs.grid.fine_span, heightmap=hm,
        requests=requests, claims=claims, topology=inputs.topology, policy=inputs.rivers,
        water_bodies=(), resolution_mode=inputs.resolution_mode, z_min=inputs.z_min,
        space=CoordinateSpace.WORLD_SURFACE_GRID,
        to_coordinate=lambda c: SurfaceGridCoord(GridX(c[0]), GridY(c[1])), control=control)
    assert_type(result, PlanBuildResult[RiverRouteBatch[SurfaceGridCoord]])


from app.application.worldData.generators.hydrology.planning.assembly.hydrologyRoutesAssembler import HydrologyRoutesAssembler
from app.application.worldData.generators.hydrology.planning.assembly.hydrologyFactsAssembler import HydrologyFactsAssembler


def hydrology_assembly_contracts(routes_owner: HydrologyRoutesAssembler, facts_owner: HydrologyFactsAssembler,
    inputs: HydrologyPlanInput, final_inputs: HydrologyFinalInput, relief: ReliefPlan,
    placement: WaterPlacementPlan, river: RiverReliefPlan, control: PlanBuildControl,
    relief_handle: RegisteredPlanContract[ReliefPlanInput, ReliefPlan],
    water_handle: RegisteredPlanContract[WaterPlacementInput, WaterPlacementPlan],
    routes_handle: RegisteredPlanContract[HydrologyPlanInput, HydrologyRoutesPlan],
    river_handle: RegisteredPlanContract[RiverReliefInput, RiverReliefPlan]) -> PlanBuildResult[HydrologyPlan]:
    HydrologyRoutesPlanProvider(relief_handle, water_handle, routes_owner)
    HydrologyFinalPlanProvider(relief_handle, routes_handle, river_handle, facts_owner)
    routes: PlanBuildResult[HydrologyRoutesPlan] = routes_owner.assemble(world_uid="world", inputs=inputs,
        relief=relief, placement=placement, control=control)
    return facts_owner.assemble(inputs=final_inputs, relief=relief, routes=routes.payload, river=river, control=control)


from app.application.worldData.generators.climate.planning.climatePlanProvider import ClimateLocalPlanProvider
from app.application.worldData.generators.climate.localFieldFromCoarse import build_local_plan_from_coarse
from app.dataModel.climate.planning.inputs.climateLocalInput import ClimateLocalInput
from app.dataModel.climate.planning.climatePlan import ClimateLocalPlan


def valid_local_provider(provider: ClimateLocalPlanProvider, request: PlanRequest[ClimateLocalInput],
    dependencies: PlanDependencyReader, control: PlanBuildControl) -> PlanBuildResult[ClimateLocalPlan]:
    return provider.build(request, dependencies, control)


def valid_local_adapter(inputs: ClimateLocalInput, base: ClimateBasePlan,
    hydrology: HydrologyPlan) -> PlanBuildResult[ClimateLocalPlan]:
    return build_local_plan_from_coarse(inputs, base, hydrology)


from app.application.worldData.planning.composition.surfacePlanningAssembler import SurfacePlanningAssembler, to_legacy_context
from app.application.worldData.planning.contracts.surfacePlanBundle import SurfacePlanBundle
from app.application.worldData.planning.contracts.surfacePlanningView import SurfacePlanningView, SurfaceTerrainContext


def valid_surface_composition(assembler: SurfacePlanningAssembler, view: SurfacePlanningView,
    wait: PlanWaitControl, working: SurfaceWorkingMaps) -> SurfaceTerrainContext | None:
    bundle: SurfacePlanBundle | None = assembler.prepare(view, wait=wait)
    return None if bundle is None else to_legacy_context(bundle, working=working)


from collections.abc import Mapping
from app.dataModel.climate.planning.climatePoints import ClimateKey, PoleClimateSample
from app.dataModel.climate.enums.climateZone import ClimateZoneProfile


def valid_surface_working(working: SurfaceWorkingMaps, gx: GridX, gy: GridY,
                          zone: ClimateKey) -> PoleClimateSample:
    assert_type(working.hydrology.fine_z_for_tile(gx, gy), Mapping[tuple[int, int], int])
    assert_type(working.climate.profile_for_key(zone), ClimateZoneProfile)
    assert_type(working.terrain.relief_z, Mapping[tuple[int, int], int])
    return working.climate.sample_pole(gx, gy)
