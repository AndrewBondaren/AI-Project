"""Positive infrastructure contracts; checked statically by Pyright."""

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_type

from app.application.cache.backends.memoryCache import MemoryCache
from app.application.cache.contracts.cacheBackend import CacheBackend, CacheBinding
from app.application.cache.service.cacheService import CacheService
from app.application.encoding.canonicalCodec import decode
from app.application.planning.providers.planProvider import PlanProvider, RegisteredPlanContract
from app.application.planning.providers.planRegistry import PlanDependencyReader, PlanRegistry
from app.application.planning.service.planningService import PlanWaitControl, PlanningService
from app.dataModel.cache.contracts.cacheEntry import CacheAdmission, CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.encoding.schemaManifest import CanonicalSchemaManifest
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import PlanSlot
from app.dataModel.spatial.grid.coordinateTypes import GridX
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext


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
