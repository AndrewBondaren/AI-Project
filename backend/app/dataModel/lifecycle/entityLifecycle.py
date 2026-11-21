from pydantic import BaseModel, ConfigDict, StrictBool

from app.dataModel.lifecycle.identity import LifecycleEntityRef, LifecycleTransitionRef


class EntityLifecycle[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")

    entity: LifecycleEntityRef[T]
    active: StrictBool
    last_transition: LifecycleTransitionRef
