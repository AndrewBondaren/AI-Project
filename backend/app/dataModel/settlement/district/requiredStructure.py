"""District template `required_structures[]` item — tz_city_generation.md §9.4."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.policy import OptionalOnWire, StrictOnWire


class RequiredStructure(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    building_template: StrictOnWire[str]
    count: OptionalOnWire[int] = 1
    position: OptionalOnWire[str] = "any"
