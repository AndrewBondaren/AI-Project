"""Typed level boundary (§3.2); no logging in dataModel."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.locations.enums.accessMechanic import AccessMechanic
from app.dataModel.locations.structure.enums.buildingPurpose import BuildingPurpose
from app.dataModel.locations.structure.room.roomDef import RoomDef


class LevelDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    z_offset: StrictOnWire[int]
    display_name: StrictOnWire[str]
    z_height: DefaultOnWire[Annotated[int, Field(ge=1)] | None] = None
    isolated: DefaultOnWire[bool] = False
    access_mechanic: DefaultOnWire[list[AccessMechanic]] = Field(default_factory=list)
    rooms: StrictOnWire[list[RoomDef]] = Field(min_length=1)
    purpose: DefaultOnWire[BuildingPurpose | None] = None
    window_z_offset: DefaultOnWire[int | None] = None
    window_z_ratio: DefaultOnWire[float | None] = None
    _height_substitution: str | None = PrivateAttr(default=None)

    @model_validator(mode="wrap")
    @classmethod
    def _height_fallback(cls, value, handler):
        try:
            return handler(value)
        except ValidationError as exc:
            if not isinstance(value, dict) or not any(error["loc"] == ("z_height",) for error in exc.errors()):
                raise
            result = handler({**value, "z_height": None})
            result._height_substitution = repr(value["z_height"])
            return result

    @property
    def height_substitution(self) -> str | None:
        return self._height_substitution


def validate_room_ids(levels: list[LevelDef]) -> None:
    seen: set[str] = set()
    for level in levels:
        local = {room.room_id for room in level.rooms}
        for room in level.rooms:
            if room.room_id in seen:
                raise ValueError(f"duplicate room_id '{room.room_id}'")
            seen.add(room.room_id)
            if room.attach_to is not None and room.attach_to not in local:
                raise ValueError(f"room '{room.room_id}': attach_to '{room.attach_to}' must exist on the same level")
