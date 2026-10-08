"""District template `required_structures[]` item — tz_city_generation.md §9.4."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictOnWire
from app.dataModel.locations.settlement.enums.requiredStructurePosition import (
    POSITION_ANY,
    POSITION_CENTER,
    RequiredStructurePosition,
)
from app.dataModel.locations.structure.building.plotLayoutTemplate import DrawingKey
from app.dataModel.locations.structure.enums.buildingPurpose import BuildingPurpose

__all__ = [
    "POSITION_ANY",
    "POSITION_CENTER",
    "RequiredStructure",
    "RequiredStructurePosition",
]


class RequiredStructure(BaseModel):
    """Pin of a plot drawing (`DrawingKey`). Not a building body, not a purpose leaf."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    plot_template: StrictOnWire[DrawingKey] = Field(
        validation_alias=AliasChoices("plot_template", "building_template"),
    )
    structure_type: DefaultWhenMissing[BuildingPurpose | None] = None
    count: DefaultWhenMissing[int] = 1
    position: DefaultWhenMissing[RequiredStructurePosition] = POSITION_ANY

    @field_validator("structure_type", mode="before")
    @classmethod
    def _coerce_purpose(cls, value: Any) -> Any:
        if value is None:
            return None
        parsed = BuildingPurpose.from_wire(value)
        if parsed is None:
            raise ValueError("unknown structure_type")
        return parsed

    @field_validator("position", mode="before")
    @classmethod
    def _coerce_position(cls, value: Any) -> Any:
        if value is None:
            return None
        parsed = RequiredStructurePosition.from_wire(value)
        if parsed is None:
            raise ValueError("unknown position")
        return parsed
