"""One `worlds.climate_zone_registry[]` row — N1-W-04."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class ClimateZoneEntry(BaseModel):
    """tz_climate.md § climate_zone_registry — profile overrides enum defaults."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_climate: StrictOnWire[str]
    base_temperature: DefaultOnWire[int | None] = None
    typical_elevation_z: DefaultOnWire[int | None] = None
    base_rainfall: DefaultOnWire[int | None] = None
    temperature_variance: DefaultOnWire[int | None] = None
    rainfall_variance: DefaultOnWire[int | None] = None
