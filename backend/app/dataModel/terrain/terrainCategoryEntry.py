"""One `worlds.terrain_category_registry[]` row — passability flags."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class TerrainCategoryEntry(BaseModel):
    """N1-W-03 — tz_locations.md § terrain_category_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_category: StrictOnWire[str]
    display_category: DefaultOnWire[str | None] = None
    passable: DefaultOnWire[bool] = True
    jumpable: DefaultOnWire[bool] = False
    climbable: DefaultOnWire[bool] = False
    breakable: DefaultOnWire[bool] = False
