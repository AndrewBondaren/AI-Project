"""Room entry wire contract — building generator §3.6."""
from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.annotationPolicy import (
    DefaultEnumOnWire, DefaultOnWire, StrictEnumOnWire, StrictOnWire,
)
from app.dataModel.constrainedField import constrained_field
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from app.dataModel.locations.structure.enums.entryAccessType import EntryAccessType
from app.dataModel.locations.transitions.transitionType import TransitionType


class EntryPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    wall: StrictOnWire[Facing]
    passage_type: StrictEnumOnWire[TransitionType]
    width: DefaultOnWire[int] = constrained_field(default=1, greater_equals=1)
    door_height: DefaultOnWire[int | None] = None
    frame_material: DefaultOnWire[str | None] = None
    panel_material: DefaultOnWire[str | None] = None
    access_type: DefaultEnumOnWire[EntryAccessType] = EntryAccessType.AUTO

    @field_validator("wall")
    @classmethod
    def _cardinal_wall(cls, value: Facing) -> Facing:
        if value not in CARDINAL_FACINGS:
            raise ValueError("entry wall must be cardinal")
        return value

    @field_validator("passage_type")
    @classmethod
    def _entrance_type(cls, value: TransitionType) -> TransitionType:
        if value not in (TransitionType.MAIN_ENTRANCE, TransitionType.SERVICE_ENTRANCE):
            raise ValueError("entry passage_type must be main_entrance or service_entrance")
        return value
