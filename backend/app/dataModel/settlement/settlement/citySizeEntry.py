"""One `worlds.city_size_registry[]` row — N1-W-08."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire


class CitySizeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_size: StrictOnWire[str]
    display_size: OptionalOnWire[str | None] = None
    map_cells_count: OptionalOnWire[int | None] = Field(default=None, ge=1, alias="radius")
    footprint_multiplier: OptionalOnWire[float | None] = Field(default=None, gt=0.0)
