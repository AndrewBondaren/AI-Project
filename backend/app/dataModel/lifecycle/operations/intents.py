from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.lifecycle.lifecycleReplacement import LifecycleReplacement


class LifecycleCreate[T, R: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    operation: Literal[LifecycleOperation.CREATE] = LifecycleOperation.CREATE
    change_uid: EntityUid
    entity: LifecycleEntityRef[T]
    reason: R


class LifecycleEnd[T, R: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    operation: Literal[LifecycleOperation.END] = LifecycleOperation.END
    change_uid: EntityUid
    entity: LifecycleEntityRef[T]
    reason: R


class LifecycleReactivate[T, R: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    operation: Literal[LifecycleOperation.REACTIVATE] = LifecycleOperation.REACTIVATE
    change_uid: EntityUid
    entity: LifecycleEntityRef[T]
    reason: R
