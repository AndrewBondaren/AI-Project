from pydantic import BaseModel, ConfigDict

from app.dataModel.lifecycle.reads.facts import AbsentLifecycle, PresentLifecycle, UnknownLifecycle, LastTransitionFact
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class LifecycleCapture[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    publication: WorldPublicationRef
    entities: tuple[AbsentLifecycle[T] | PresentLifecycle[T] | UnknownLifecycle[T], ...]
    last_transitions: tuple[LastTransitionFact[T], ...]
