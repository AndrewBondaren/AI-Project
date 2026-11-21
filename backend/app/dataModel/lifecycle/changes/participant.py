from pydantic import BaseModel, ConfigDict

from app.dataModel.lifecycle.entityLifecycle import EntityLifecycle
from app.dataModel.lifecycle.reads.facts import AbsentLifecycle, PresentLifecycle


class ParticipantTransition[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    before: AbsentLifecycle[T] | PresentLifecycle[T]
    after: EntityLifecycle[T]
