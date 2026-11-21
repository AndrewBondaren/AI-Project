from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.lifecycle.changes.participant import ParticipantTransition


class LifecycleTransition[T, I: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    intent: I
    participants: tuple[ParticipantTransition[T], ...] = Field(min_length=1)
