"""One `worlds.terrain_registry[]` row — cell terrain type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class TerrainRegistryEntry(BaseModel):
    """N1-W-02 — tz_locations.md § terrain_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_terrain: StrictOnWire[str]
    glossary_ref: DefaultOnWire[str | None] = None
    terrain_category: StrictOnWire[str]
    travel_modifier: DefaultOnWire[float | None] = None
    danger_level: DefaultOnWire[str] = "none"
    has_state: DefaultOnWire[bool] = False
    default_state: DefaultOnWire[str | None] = None
    default_material: DefaultOnWire[str | None] = None
    gap_width: DefaultOnWire[int | None] = constrained_field(default=None, greater_equals=1)
