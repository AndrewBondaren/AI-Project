"""One `worlds.room_type_registry[]` row — N1-W room types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire


class RoomTypeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_room: StrictOnWire[str]
    glossary_ref: OptionalOnWire[str | None] = None
