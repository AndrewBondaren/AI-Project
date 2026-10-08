"""One `worlds.terrain_registry[]` row — cell terrain type."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.registryKey import RegistryKey

if TYPE_CHECKING:
    from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


class TerrainRegistryEntry(BaseModel):
    """N1-W-02 — tz_locations.md § terrain_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_terrain: StrictOnWire[RegistryKey[WorldTerrainRegistry]]
    glossary_ref: DefaultWhenMissing[str | None] = None
    terrain_category: StrictOnWire[str]
    travel_modifier: DefaultWhenMissing[float | None] = None
    danger_level: DefaultWhenMissing[str] = "none"
    has_state: DefaultWhenMissing[bool] = False
    default_state: DefaultWhenMissing[str | None] = None
    default_material: DefaultWhenMissing[str | None] = None
    gap_width: DefaultWhenMissing[Annotated[int, Field(ge=1)] | None] = constrained_field(default=None)
