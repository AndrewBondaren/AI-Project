"""District template `required_structures[]` item — tz_city_generation.md §9.4."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class RequiredStructure(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    building_template: StrictOnWire[str]
    count: DefaultOnWire[int] = 1
    position: DefaultOnWire[str] = "any"
