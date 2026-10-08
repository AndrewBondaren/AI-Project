"""Declared lake shoreline — SCH-WORLD-HYDROLOGY."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint


class DeclaredLake(BaseModel):
    """Master declare: closed-ish lake shoreline polyline."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: StrictOnWire[str]
    shoreline: DefaultWhenMissing[list[HydrologyWaypoint]] = Field(default_factory=list)
