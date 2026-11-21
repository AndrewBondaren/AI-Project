from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.dataModel.lifecycle.identity import LifecycleEntityRef, LifecycleTransitionRef
from app.dataModel.lifecycle.entityLifecycle import EntityLifecycle
from app.dataModel.lifecycle.operations.kind import LifecycleOperation


class UnknownFactCause(StrEnum):
    NOT_CAPTURED = "not_captured"
    INCOMPLETE_HISTORY = "incomplete_history"


class AbsentLifecycle[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    status: Literal["absent"] = "absent"
    entity: LifecycleEntityRef[T]


class PresentLifecycle[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    status: Literal["present"] = "present"
    state: EntityLifecycle[T]


class UnknownLifecycle[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    status: Literal["unknown"] = "unknown"
    entity: LifecycleEntityRef[T]
    cause: UnknownFactCause


class LastTransitionFact[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    ref: LifecycleTransitionRef
    operation: LifecycleOperation
    entity: LifecycleEntityRef[T]
