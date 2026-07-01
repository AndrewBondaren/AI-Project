"""One `worlds.terrain_category_registry[]` row — passability flags."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import OptionalOnWire, StrictOnWire


class TerrainCategoryEntry(BaseModel):
    """N1-W-03 — tz_locations.md § terrain_category_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_category: StrictOnWire[str]
    display_category: OptionalOnWire[str | None] = None
    passable: OptionalOnWire[bool] = True
    jumpable: OptionalOnWire[bool] = False
    climbable: OptionalOnWire[bool] = False
    breakable: OptionalOnWire[bool] = False
