"""State of one side; owner is independent of endpoint host and parent."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.locations.transitions.transitionEndpoint import EndpointRef


type SideOverride = Annotated[StrictInt, Field(ge=0, le=100)]


class TransitionSideId(StrEnum):
    A = "a"
    B = "b"


class TransitionSide(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_location_uid: DefaultOnWire[EndpointRef | None] = None
    is_discovered: DefaultOnWire[bool] = True
    is_accessible: DefaultOnWire[bool] = True
    entry_difficulty_override: DefaultOnWire[SideOverride | None] = None
    guard_level_override: DefaultOnWire[SideOverride | None] = None
    display_name: DefaultOnWire[str | None] = None
