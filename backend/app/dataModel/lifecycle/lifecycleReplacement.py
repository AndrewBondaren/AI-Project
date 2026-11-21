from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation


class LifecycleReplacement[T, R: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    operation: Literal[LifecycleOperation.REPLACEMENT] = LifecycleOperation.REPLACEMENT
    change_uid: EntityUid
    predecessors: tuple[LifecycleEntityRef[T], ...] = Field(min_length=1)
    successors: tuple[LifecycleEntityRef[T], ...] = Field(min_length=1)
    reason: R
