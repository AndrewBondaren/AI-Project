"""District `placement_conditions[]` item — tz_city_generation.md §9.3."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire


class PlacementCondition(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: StrictOnWire[str]
    terrain_types: OptionalOnWire[list[str] | None] = None
    min_count: OptionalOnWire[int | None] = None
    size: OptionalOnWire[str | None] = None
    tier: OptionalOnWire[str | None] = None
    district_type: OptionalOnWire[str | None] = None
    zone: OptionalOnWire[str | None] = None
