"""Typed input for a single pinned window read."""
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.planning.identity.planRef import PlanRef
from app.dataModel.spatial.query.window import SpatialWindow
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef


type SpatialReadRevision = PlanRef | WorldPublicationRef


class SpatialReadMode(StrEnum):
    REQUIRED = "required"
    PREVIEW = "preview"


class SpatialReadRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    request_id: UUID
    window: SpatialWindow
    revision: SpatialReadRevision
    mode: SpatialReadMode

    @field_validator("revision", mode="before")
    @classmethod
    def typed_revision(cls, value: object) -> object:
        if not isinstance(value, (PlanRef, WorldPublicationRef)):
            raise ValueError("expected a typed read revision")
        return value
