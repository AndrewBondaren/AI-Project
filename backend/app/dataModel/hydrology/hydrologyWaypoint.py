"""Hydrology declare waypoint — meters, SCH-WORLD-HYDROLOGY."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import StrictOnWire


class HydrologyWaypoint(BaseModel):
    """Surface waypoint in world meters (x/y/z)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    x: StrictOnWire[int]
    y: StrictOnWire[int]
    z: StrictOnWire[int] = 0
