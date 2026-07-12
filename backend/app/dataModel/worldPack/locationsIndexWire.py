"""locations_index.json wire — L1 pins mirror for world map (WP-9)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class LocationsIndexPin(BaseModel):
    """Single location pin on the world map index."""

    SCHEMA_ID: ClassVar[str] = "SCH-LOCATIONS-INDEX-PIN"

    model_config = ConfigDict(extra="ignore", frozen=True)

    location_uid: str
    map_x: int
    map_y: int
    map_z: int = 0
    display_name: str | None = None
    system_location_type: str | None = None


class LocationsIndexWire(BaseModel):
    """Root of ``locations_index.json``."""

    SCHEMA_ID: ClassVar[str] = "SCH-LOCATIONS-INDEX-WIRE"

    model_config = ConfigDict(extra="ignore", frozen=True)

    locations: list[LocationsIndexPin] = Field(default_factory=list)
