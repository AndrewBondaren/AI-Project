from typing import Self
from pydantic import BaseModel, ConfigDict, model_validator
from app.dataModel.lifecycle.changes.preparedInvariants import validate_prepared

from app.dataModel.lifecycle.operations.intents import LifecycleEnd
from app.dataModel.lifecycle.changes.transition import LifecycleTransition
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class PreparedLifecycleEnd[T, R: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    base: WorldPublicationRef
    transition: LifecycleTransition[T, LifecycleEnd[T, R]]

    @model_validator(mode="after")
    def coherent_transition(self) -> Self:
        return validate_prepared(self)
