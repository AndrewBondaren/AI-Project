"""One `worlds.terrain_registry[]` row — cell terrain type."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field


class TerrainRegistryEntry(BaseModel):
    """N1-W-02 — tz_locations.md § terrain_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_terrain: StrictOnWire[str]
    glossary_ref: OptionalOnWire[str | None] = None
    terrain_category: StrictOnWire[str]
    travel_modifier: OptionalOnWire[float | None] = None
    danger_level: OptionalOnWire[str] = "none"
    has_state: OptionalOnWire[bool] = False
    default_state: OptionalOnWire[str | None] = None
    default_material: OptionalOnWire[str | None] = None
    gap_width: OptionalOnWire[int | None] = constrained_field(default=None, greater_equals=1)
