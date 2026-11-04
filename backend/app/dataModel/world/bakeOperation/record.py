from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, TypeAdapter

from app.dataModel.engine.dag.identity import ExecutionIdValue, InvocationIdValue, Ordinal
from app.dataModel.identity.uid import EntityUid
from app.dataModel.world.bakeOperation.request import BakeRequest


_uid = TypeAdapter[str](EntityUid)


@dataclass(frozen=True, slots=True)
class PublicationOperationId:
    value: str

    def __post_init__(self) -> None:
        if isinstance(self.value, StrEnum):
            raise TypeError("publication operation ID cannot be a StrEnum")
        _uid.validate_python(self.value, strict=True)

    @classmethod
    def require(cls, value: object) -> Self:
        if not isinstance(value, cls):
            raise TypeError("expected a PublicationOperationId")
        return value

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


class BakeErrorKind(StrEnum):
    PREPARATION_FAILED = "PREPARATION_FAILED"
    PUBLICATION_ROLLED_BACK = "PUBLICATION_ROLLED_BACK"
    LEGACY = "LEGACY"


class BakeError(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    kind: BakeErrorKind
    message: str

    @staticmethod
    def encode(value: object) -> bytes:
        if not isinstance(value, BakeError):
            raise TypeError("expected a BakeError")
        return value.model_dump_json().encode("utf-8")

    @classmethod
    def decode(cls, stored: bytes | str) -> Self:
        # Existing rows store arbitrary diagnostic text. New envelopes use SQLite BLOB.
        if isinstance(stored, str):
            return cls(kind=BakeErrorKind.LEGACY, message=stored)
        return cls.model_validate_json(stored)


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
    error: BakeError | None
    publication_operation_id: PublicationOperationId | None
