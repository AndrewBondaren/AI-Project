"""One `worlds.climate_zone_registry[]` row — N1-W-04."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire


class ClimateZoneEntry(BaseModel):
    """tz_climate.md § climate_zone_registry — profile overrides enum defaults."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_climate: StrictOnWire[str]
    base_temperature: OptionalOnWire[int | None] = None
    typical_elevation_z: OptionalOnWire[int | None] = None
    base_rainfall: OptionalOnWire[int | None] = None
    temperature_variance: OptionalOnWire[int | None] = None
    rainfall_variance: OptionalOnWire[int | None] = None
