"""One `worlds.weather_type_registry[]` row — N1-W-05."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class WeatherTypeEntry(BaseModel):
    """tz_climate.md § Runtime weather; project_data_storage_tz.md."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_weather: StrictOnWire[str]
    display_weather: OptionalOnWire[str | None] = None
    temp_max: OptionalOnWire[int | None] = None
    temp_min: OptionalOnWire[int | None] = None
    rainfall_min: OptionalOnWire[int | None] = None
    priority: OptionalOnWire[int] = constrained_field(default=99, greater_equals=1)
    travel_modifier: OptionalOnWire[float] = constrained_field(default=1.0, greater=0.0)
    need_modifiers: OptionalOnWire[dict[str, int]] = Field(default_factory=dict)
    glossary_ref: OptionalOnWire[str | None] = None
