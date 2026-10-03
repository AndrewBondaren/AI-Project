"""Simplified building template room slot — locations.md inline / template import."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.shared.ranges import IntMinMax


class BuildingTemplateRoomSlot(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_room: StrictOnWire[str]
    required: DefaultOnWire[bool] = True
    count: DefaultOnWire[IntMinMax | None] = None
