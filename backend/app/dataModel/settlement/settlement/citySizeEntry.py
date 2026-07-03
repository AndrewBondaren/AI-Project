"""One `worlds.city_size_registry[]` row — N1-W-08."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class CitySizeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_size: StrictOnWire[str]
    display_size: DefaultOnWire[str | None] = None
    map_cells_count: DefaultOnWire[int | None] = constrained_field(
        default=None, greater_equals=1, alias="radius",
    )
    footprint_multiplier: DefaultOnWire[float | None] = constrained_field(default=None, greater=0.0)
