"""Declared coastline / sea basin shore — SCH-WORLD-HYDROLOGY."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.hydrology.hydrologyWaypoint import HydrologyWaypoint


class DeclaredCoastline(BaseModel):
    """Master declare: open coastline polyline; role from location subtype."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: StrictOnWire[str]
    path: DefaultOnWire[list[HydrologyWaypoint]] = Field(default_factory=list)
