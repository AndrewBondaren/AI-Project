from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.identity.uid import EntityUid
from app.dataModel.lifecycle.evidence.effects import DomainEffect
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class DomainAdmission[T](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    publication: WorldPublicationRef
    action_uid: EntityUid
    effects: tuple[DomainEffect[T], ...] = Field(min_length=1)
