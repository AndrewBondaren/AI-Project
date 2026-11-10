from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.cache.contracts.cacheEntry import CacheEntry
from app.dataModel.cache.identity.cacheKey import CacheKey
from app.dataModel.engine.dag.identity import ExecutionIdValue, InvocationIdValue


class _Record(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")


class ManifestPinRead(_Record):
    store_id: UUID
    execution_id: ExecutionIdValue
    invocation_id: InvocationIdValue
    logical_read_key: Annotated[str, Field(min_length=1)]
    pin_id: Annotated[str, Field(min_length=1)]
    world_uid: Annotated[str, Field(min_length=1)]
    max_bytes: PositiveInt


class ManifestAddress(_Record):
    ref: ArtifactRef
    key: CacheKey[bytes]


class ManifestStorageRead(_Record):
    pin: ManifestPinRead
    address: ManifestAddress


class ManifestCachedRead(ManifestStorageRead):
    entry: CacheEntry[bytes]


class VerifiedManifestBytes(_Record):
    ref: ArtifactRef
    payload: bytes


class ManifestReadReason(StrEnum):
    CLOSED_PIN = "closed_pin"
    INVALID_PIN = "invalid_pin"
    MISSING_HOLD = "missing_hold"
    UNSEALED = "unsealed"
    IDENTITY_MISMATCH = "identity_mismatch"
    BUDGET_EXCEEDED = "budget_exceeded"
    INVALID_MANIFEST = "invalid_manifest"


class ManifestReadRefusal(_Record):
    pin_id: str
    ref: ArtifactRef | None = None
    reason: ManifestReadReason
