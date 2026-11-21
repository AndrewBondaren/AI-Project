from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.identity import LifecycleEntityRef


LifecycleEffectKind = Literal["create", "end", "reactivate"]


class DomainEffect[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    entity: LifecycleEntityRef[T]
    effect: LifecycleEffectKind
    reason_action_uid: EntityUid
