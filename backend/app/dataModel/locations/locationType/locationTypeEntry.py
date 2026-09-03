"""One `worlds.location_type_registry[]` row — N1-W-07."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.locations.locationType.locationTypeSubtypeEntry import LocationTypeSubtypeEntry


class LocationTypeEntry(BaseModel):
    """tz_locations.md § location_type_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_type: StrictOnWire[str]
    # validation_alias — wire contract on POJO (not generator hardcode): canonical
    # key display_type; display_name — legacy import alias (tz_locations.md § registry).
    display_type: StrictOnWire[str] = Field(
        validation_alias=AliasChoices("display_type", "display_name"),
    )
    parent_types: DefaultOnWire[list[str | None]] = Field(default_factory=list)
    is_outdoor: DefaultOnWire[bool | None] = None
    subtypes: DefaultOnWire[list[LocationTypeSubtypeEntry]] = Field(default_factory=list)

    def fixture_identity(self) -> LocationTypeEntry:
        """world_template row: system/display only (JV fills the rest)."""
        return LocationTypeEntry(system_type=self.system_type, display_type=self.display_type)
