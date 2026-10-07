"""One `location_type_registry[].subtypes[]` row — N1-W-07a."""

from __future__ import annotations

from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from app.dataModel.annotationPolicy import DefaultOnWire, IgnoreOnWire, StrictOnWire


class LocationTypeSubtypeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    system_subtype: StrictOnWire[str]
    display_subtype: DefaultOnWire[str | None] = None
    border_category: DefaultOnWire[str | None] = None
    # None inherits the engine symbol; length constraints apply only to strings.
    l0_map_symbol: DefaultOnWire[Annotated[str, Field(min_length=1, max_length=1)] | None] = None
    # Settlement recipe only (CITY-T-2d). Geographic subtypes may carry the keys; generate ignores them.
    typical_district_types: DefaultOnWire[list[str]] = Field(default_factory=list)
    required_structure_types: DefaultOnWire[list[str]] = Field(default_factory=list)
    # Settlement morphology × rank (LOC-T-2). Empty on geographic / district / building subtypes.
    footprint_by_size: DefaultOnWire[dict[str, float]] = Field(default_factory=dict)
    # Recipe default for an instance's SettlementPayload; no generation gate here.
    # None inherits the type setting; False is an explicit override.
    is_inhabited: IgnoreOnWire[bool | None] = None

    @model_serializer(mode="wrap")
    def serialize_overrides(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = handler(self)
        # Omitted world overrides must remain omitted after persistence;
        # explicit empty recipe lists still clear the engine recipe.
        for name in ("is_inhabited", "typical_district_types", "required_structure_types"):
            if name not in self.model_fields_set:
                data.pop(name, None)
        return data

    def has_district_recipe(self) -> bool:
        """Non-empty typical district types → recipe path; empty → legacy district select."""
        return bool(self.typical_district_types)
