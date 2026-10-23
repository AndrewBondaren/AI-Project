"""Every marked line must produce its specified pyright diagnostic."""

from app.dataModel.cache.contracts.cacheContract import CacheContract
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.planning.contracts.planEnvelope import PlanEnvelope
from app.dataModel.planning.contracts.planRequest import PlanRequest
from app.dataModel.planning.identity.planKey import InputFingerprint, OutputFingerprint, SchemaVersion
from app.dataModel.cache.contracts.cacheContract import CacheSchemaVersion
from app.dataModel.spatial.grid.coordinateTypes import FineX
from app.dataModel.climate.planning.climatePlan import ClimateBasePlan, ClimateLocalPlan
from app.dataModel.terrain.planning.terrainPlan import TerrainPlan
from tests.typing.planning.valid import (
    ClimatePayload, HydroInput, HydroPayload, build_climate, require_climate, require_grid_x,
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
