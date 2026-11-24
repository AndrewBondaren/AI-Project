from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.identity import LifecycleEntityRef
from app.dataModel.lifecycle.operations.kind import LifecycleOperation


LifecycleEffectKind = Literal[LifecycleOperation.CREATE, LifecycleOperation.END, LifecycleOperation.REACTIVATE]


class DomainEffect[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    entity: LifecycleEntityRef[T]
    effect: LifecycleEffectKind
    reason_action_uid: EntityUid

    @field_validator("effect", mode="before")
    @classmethod
    def require_enum_member(cls, value: object) -> object:
        if type(value) is not LifecycleOperation:
            raise ValueError("effect requires a LifecycleOperation enum member")
        return value
