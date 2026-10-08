"""One `worlds.location_type_registry[]` row — N1-W-07."""

from __future__ import annotations

from typing import Any
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from app.dataModel.annotationPolicy import DefaultWhenMissing, IgnoreOnWire, StrictOnWire
from app.dataModel.locations.locationType.locationTypeSubtypeEntry import LocationTypeSubtypeEntry
from app.dataModel.locations.payloadKind import PayloadKind


class LocationTypeEntry(BaseModel):
    """tz_locations.md § location_type_registry."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    system_type: StrictOnWire[str]
    # validation_alias — wire contract on POJO (not generator hardcode): canonical
    # key display_type; display_name — legacy import alias (tz_locations.md § registry).
    display_type: StrictOnWire[str] = Field(
        validation_alias=AliasChoices("display_type", "display_name"),
    )
    parent_types: DefaultWhenMissing[list[str | None]] = Field(default_factory=list)
    is_outdoor: DefaultWhenMissing[bool | None] = None
    payload_kind: DefaultWhenMissing[PayloadKind | None] = None
    # Keep omission distinct from an explicit False in world overlays.
    is_inhabited: IgnoreOnWire[bool] = False
    subtypes: DefaultWhenMissing[list[LocationTypeSubtypeEntry]] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def serialize_overrides(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = handler(self)
        # An omitted override must survive world JSON normalization as omitted.
        if "is_inhabited" not in self.model_fields_set:
            data.pop("is_inhabited", None)
        return data

    def fixture_identity(self) -> LocationTypeEntry:
        """world_template row: system/display only (JV fills the rest)."""
        return LocationTypeEntry(system_type=self.system_type, display_type=self.display_type,
                                 payload_kind=self.payload_kind, is_inhabited=self.is_inhabited)
