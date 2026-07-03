"""One `location_type_registry[].subtypes[]` row — N1-W-07a."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class LocationTypeSubtypeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_subtype: StrictOnWire[str]
    display_subtype: DefaultOnWire[str | None] = None
    border_category: DefaultOnWire[str | None] = None
