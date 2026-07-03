"""One `worlds.road_settings[]` row — per connection_type defaults."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class RoadSettingsEntry(BaseModel):
    """Settings for a single transport connection_type — tz_structure_connections.md §3.6."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_connection_type: StrictOnWire[str] = Field(alias="connection_type")
    curve_radius_factor: DefaultOnWire[int] = constrained_field(default=1, greater_equals=1)
    max_segment_length_m: DefaultOnWire[int] = constrained_field(default=30, greater_equals=1)
    min_segment_length_m: DefaultOnWire[int] = constrained_field(default=3, greater_equals=1)
    default_lanes_per_side: DefaultOnWire[int | None] = None
    auto_sidewalk: DefaultOnWire[bool] = False
    base_travel_modifier: DefaultOnWire[float] = constrained_field(default=1.0, greater=0.0)
    condition_degradation: DefaultOnWire[float] = constrained_field(default=0.2, greater_equals=0.0)

    @classmethod
    def fallback(cls) -> RoadSettingsEntry:
        """Field-level builtins for unknown/missing ``connection_type``."""
        return cls(
            system_connection_type="__unknown__",
            default_lanes_per_side=1,
        )
