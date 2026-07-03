"""District `placement_conditions[]` item — tz_city_generation.md §9.3."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class PlacementCondition(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    type: StrictOnWire[str]
    terrain_types: DefaultOnWire[list[str] | None] = None
    min_count: DefaultOnWire[int | None] = None
    size: DefaultOnWire[str | None] = None
    tier: DefaultOnWire[str | None] = None
    district_type: DefaultOnWire[str | None] = None
    zone: DefaultOnWire[str | None] = None
