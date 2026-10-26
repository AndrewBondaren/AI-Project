"""State of one side; owner is independent of endpoint host and parent."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.annotationPolicy import DefaultWhenMissing
from app.dataModel.locations.transitions.transitionEndpoint import EndpointRef


type SideOverride = Annotated[StrictInt, Field(ge=0, le=100)]


class TransitionSideId(StrEnum):
    SOURCE = "source"
    DESTINATION = "destination"


class TransitionSide(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_location_uid: DefaultWhenMissing[EndpointRef | None] = None
    is_discovered: DefaultWhenMissing[bool] = True
    is_accessible: DefaultWhenMissing[bool] = True
    entry_difficulty_override: DefaultWhenMissing[SideOverride | None] = None
    guard_level_override: DefaultWhenMissing[SideOverride | None] = None
    display_name: DefaultWhenMissing[str | None] = None
