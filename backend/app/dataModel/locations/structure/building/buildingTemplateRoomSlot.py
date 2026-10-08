"""Simplified building template room slot — locations.md inline / template import."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.shared.ranges import IntMinMax


class BuildingTemplateRoomSlot(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_room: StrictOnWire[str]
    required: DefaultWhenMissing[bool] = True
    count: DefaultWhenMissing[IntMinMax | None] = None
