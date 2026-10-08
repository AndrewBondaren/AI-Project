"""Horizontal room-to-room connection wire contract — building generator §3.7."""
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictEnumOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.locations.transitions.transitionType import TransitionType

DEFAULT_DOORWAY_WIDTH = 1
DEFAULT_ARCHWAY_WIDTH = 2


class RoomConnection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    from_room:        StrictOnWire[str]
    to_room:          StrictOnWire[str]
    passage_type:     StrictEnumOnWire[TransitionType]
    required:         DefaultWhenMissing[bool] = False
    width:            DefaultWhenMissing[int] = constrained_field(
        default=DEFAULT_DOORWAY_WIDTH, greater_equals=1,
    )
    door_height:      DefaultWhenMissing[int | None] = None
    frame_material:   DefaultWhenMissing[str | None] = None
    panel_material:   DefaultWhenMissing[str | None] = None
    step_material:    DefaultWhenMissing[str | None] = None
    railing_material: DefaultWhenMissing[str | None] = None

    @field_validator("passage_type", mode="before")
    @classmethod
    def _horizontal_type(cls, value: Any) -> Any:
        """Only horizontal passage types belong to this contract."""
        try:
            parsed = TransitionType(value)
        except (ValueError, TypeError):
            parsed = None
        if parsed in (TransitionType.DOORWAY, TransitionType.ARCHWAY):
            return parsed
        raise ValueError("passage_type must be doorway or archway")

    @model_validator(mode="after")
    def _resolve_width_default(self) -> "RoomConnection":
        if "width" not in self.model_fields_set and self.passage_type is TransitionType.ARCHWAY:
            object.__setattr__(self, "width", DEFAULT_ARCHWAY_WIDTH)
        return self
