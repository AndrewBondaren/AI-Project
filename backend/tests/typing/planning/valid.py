"""Typed contracts preserve I/T, nominal units and covariant diagnostic context."""

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
from app.dataModel.spatial.grid.coordinateTypes import GridX
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput
from app.dataModel.terrain.relief.planning.reliefPlan import ReliefPlan, RiverBedRecord
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
