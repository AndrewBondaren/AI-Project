"""Typed level boundary (§3.2); no logging in dataModel."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.locations.enums.accessMechanic import AccessMechanic
from app.dataModel.locations.structure.enums.buildingPurpose import BuildingPurpose
from app.dataModel.locations.structure.room.roomDef import RoomDef


class LevelDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    z_offset: StrictOnWire[int]
    display_name: StrictOnWire[str]
    z_height: DefaultWhenMissing[Annotated[int, Field(ge=1)] | None] = None
    isolated: DefaultWhenMissing[bool] = False
    access_mechanic: DefaultWhenMissing[list[AccessMechanic]] = Field(default_factory=list)
    rooms: StrictOnWire[list[RoomDef]] = Field(min_length=1)
    purpose: DefaultWhenMissing[BuildingPurpose | None] = None
    window_z_offset: DefaultWhenMissing[int | None] = None
    window_z_ratio: DefaultWhenMissing[float | None] = None
    _height_substitution: str | None = PrivateAttr(default=None)

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
