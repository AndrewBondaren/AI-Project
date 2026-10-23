"""Typed contracts preserve I/T, nominal units and covariant diagnostic context."""

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_type

from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.contracts.cacheLookup import CacheHit, CacheLookup
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.spatial.grid.coordinateTypes import GridX
from app.dataModel.validation.diagnostics.runtimeIssueContext import RuntimeIssueContext
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan
from app.dataModel.climate.planning.inputs.climateBaseInput import ClimateBaseInput
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from app.dataModel.terrain.planning.inputs.terrainBaseInput import TerrainBaseInput


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
