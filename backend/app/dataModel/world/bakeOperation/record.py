from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, TypeAdapter

from app.dataModel.engine.dag.identity import ExecutionIdValue, InvocationIdValue, Ordinal
from app.dataModel.identity.uid import EntityUid
from app.dataModel.world.bakeOperation.request import BakeRequest


_uid = TypeAdapter[str](EntityUid)


class PublicationOperationId(str):
    def __new__(cls, value: str) -> "PublicationOperationId":
        if isinstance(value, StrEnum):
            raise TypeError("publication operation ID cannot be a StrEnum")
        return super().__new__(cls, _uid.validate_python(value, strict=True))


class BakeStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PUBLISHING = "PUBLISHING"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Waiter(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    execution_id: ExecutionIdValue
    invocation_id: InvocationIdValue
    step_index: Ordinal


class DeliveryStatus(StrEnum):
    SUBSCRIBED = "SUBSCRIBED"
    DETACHED = "DETACHED"
    DELIVERED = "DELIVERED"


class BakeResult(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    result_ref: EntityUid


@dataclass(frozen=True)
class RolledBack:
    reason: str


@dataclass(frozen=True)
class BakeOwner:
    operation_id: str
    owner_id: str
    fence: int


@dataclass(frozen=True)
class BakeRecord:
    request: BakeRequest
    status: BakeStatus
    result: BakeResult | None
    error: str | None
    publication_operation_id: PublicationOperationId | None
