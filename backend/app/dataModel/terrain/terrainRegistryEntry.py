"""One `worlds.terrain_registry[]` row — cell terrain type."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.registryKey import RegistryKey
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.hillPolicy import HillPolicy

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
    merge_rank: DefaultWhenMissing[int] = 0
    eligibility: DefaultWhenMissing[list[EligibilityRule]] = Field(default_factory=list)
    inertia: DefaultWhenMissing[float] = Field(default=1.0, gt=0, allow_inf_nan=False)
    hills: DefaultWhenMissing[HillPolicy | None] = None

    supports_open_land_grade: DefaultWhenMissing[bool] = False
    open_land_profile: DefaultWhenMissing[Literal["plains", "forest"] | None] = None

    @model_validator(mode="after")
    def _open_land_contract(self) -> TerrainRegistryEntry:
        if self.supports_open_land_grade != (self.open_land_profile is not None):
            raise ValueError("open_land_profile is required exactly when supports_open_land_grade is true")
        return self
