"""Horizontal room-to-room connection wire contract — building generator §3.7."""
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.structure.enums.passageType import PassageType

DEFAULT_DOORWAY_WIDTH = 1
DEFAULT_ARCHWAY_WIDTH = 2


class RoomConnection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    from_room:        StrictOnWire[str]
    to_room:          StrictOnWire[str]
    passage_type:     StrictEnumOnWire[PassageType]
    required:         DefaultOnWire[bool] = False
    width:            DefaultOnWire[int] = constrained_field(
        default=DEFAULT_DOORWAY_WIDTH, greater_equals=1,
    )
    door_height:      DefaultOnWire[int | None] = None
    frame_material:   DefaultOnWire[str | None] = None
    panel_material:   DefaultOnWire[str | None] = None
    step_material:    DefaultOnWire[str | None] = None
    railing_material: DefaultOnWire[str | None] = None

    @field_validator("passage_type", mode="before")
    @classmethod
    def _horizontal_type(cls, value: Any) -> Any:
        """Non-horizontal wire falls back to doorway (§3.7); boundary logs ERROR."""
        parsed = PassageType.from_wire(value)
        if parsed in (PassageType.DOORWAY, PassageType.ARCHWAY):
            return parsed
        return PassageType.DOORWAY

    @model_validator(mode="after")
    def _resolve_width_default(self) -> "RoomConnection":
        if "width" not in self.model_fields_set and self.passage_type is PassageType.ARCHWAY:
            object.__setattr__(self, "width", DEFAULT_ARCHWAY_WIDTH)
        return self
