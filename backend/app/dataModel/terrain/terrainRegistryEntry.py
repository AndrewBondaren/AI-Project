"""One `worlds.terrain_registry[]` row — cell terrain type."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self
from copy import replace

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire, DefaultEnumWhenMissing, StrictEnumOnWire
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.constrainedField import constrained_field
from app.dataModel.registryKey import RegistryKey
from app.dataModel.terrain.eligibilityRule import EligibilityRule
from app.dataModel.terrain.hillPolicy import HillPolicy
from app.dataModel.terrain.enums.terrainFillRole import TerrainFillRole

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
    fill_roles: DefaultWhenMissing[tuple[StrictEnumOnWire[TerrainFillRole], ...]] = ()
    fill_priority: DefaultWhenMissing[int] = 0
    morph_hydrology_role: DefaultEnumWhenMissing[HydrologyCellRole | None] = None

    supports_open_land_grade: DefaultWhenMissing[bool] = False
    open_land_profile: DefaultWhenMissing[Literal["plains", "forest"] | None] = None

    @property
    def has_authored_hills(self) -> bool:
        return "hills" in self.model_fields_set

    @classmethod
    def authored_hills_key_from_wire(cls, raw: object) -> RegistryKey[WorldTerrainRegistry] | None:
        """Projection of this model's authored wire, before defaults are filled."""
        if not isinstance(raw, dict) or "hills" not in raw:
            return None
        key = raw.get("system_terrain")
        return RegistryKey(key) if isinstance(key, str) else None

    def with_hills(self, hills: HillPolicy | None) -> Self:
        return replace(self, hills=hills)

    def with_eligibility(self, rules: list[EligibilityRule]) -> Self:
        return replace(self, eligibility=list(rules))

    @model_validator(mode="after")
    def _open_land_contract(self) -> TerrainRegistryEntry:
        if self.morph_hydrology_role not in (None, HydrologyCellRole.LAKE):
            raise ValueError("region morph supports lake only; sea/river need separate contracts")
        if self.supports_open_land_grade != (self.open_land_profile is not None):
            raise ValueError("open_land_profile is required exactly when supports_open_land_grade is true")
        return self
