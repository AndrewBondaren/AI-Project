"""One `worlds.road_settings[]` row — per connection_type defaults."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy import OptionalOnWire, StrictOnWire


class RoadSettingsEntry(BaseModel):
    """Settings for a single transport connection_type — tz_structure_connections.md §3.6."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_connection_type: StrictOnWire[str] = Field(alias="connection_type")
    curve_radius_factor: OptionalOnWire[int] = Field(default=1, ge=1)
    max_segment_length_m: OptionalOnWire[int] = Field(default=30, ge=1)
    min_segment_length_m: OptionalOnWire[int] = Field(default=3, ge=1)
    default_lanes_per_side: OptionalOnWire[int | None] = None
    auto_sidewalk: OptionalOnWire[bool] = False
    base_travel_modifier: OptionalOnWire[float] = Field(default=1.0, gt=0.0)
    condition_degradation: OptionalOnWire[float] = Field(default=0.2, ge=0.0)
