"""One `location_type_registry[].subtypes[]` row — N1-W-07a."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire


class LocationTypeSubtypeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_subtype: StrictOnWire[str]
    display_subtype: DefaultOnWire[str | None] = None
    border_category: DefaultOnWire[str | None] = None
    l0_map_symbol: DefaultOnWire[str | None] = Field(
        default=None, min_length=1, max_length=1,
    )
    # Settlement recipe only (CITY-T-2d). Geographic subtypes may carry the keys; generate ignores them.
    typical_district_types: DefaultOnWire[list[str]] = Field(default_factory=list)
    required_structure_types: DefaultOnWire[list[str]] = Field(default_factory=list)

    def has_district_recipe(self) -> bool:
        """Non-empty typical district types → recipe path; empty → legacy district select."""
        return bool(self.typical_district_types)
