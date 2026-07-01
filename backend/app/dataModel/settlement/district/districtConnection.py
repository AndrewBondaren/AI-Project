"""District template `connections[]` item — tz_city_generation.md §9.5.1."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.policy import OptionalOnWire, StrictOnWire


class DistrictConnection(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    connection_type: StrictOnWire[str]
    role: OptionalOnWire[str | None] = None
    sidewalk: OptionalOnWire[bool | None] = None
    lanes_per_side: OptionalOnWire[int | None] = None
