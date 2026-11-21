from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.dataModel.lifecycle.identity import LifecycleTransitionRef
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


class AcceptedChangesQuery(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    publication: WorldPublicationRef
    refs: tuple[LifecycleTransitionRef, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_scoped_refs(self) -> Self:
        if len(set(self.refs)) != len(self.refs):
            raise ValueError("accepted-change query refs must be unique")
        if any(ref.world_uid != self.publication.world_uid for ref in self.refs):
            raise ValueError("accepted-change refs must belong to the queried world")
        return self


class AcceptedChangeAbsent(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal["absent"] = "absent"
    ref: LifecycleTransitionRef


class AcceptedChangeFound[C: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    kind: Literal["found"] = "found"
    ref: LifecycleTransitionRef
    transition: C


class AcceptedChangesResult[E: BaseModel](BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", revalidate_instances="always")
    publication: WorldPublicationRef
    entries: tuple[E, ...]
