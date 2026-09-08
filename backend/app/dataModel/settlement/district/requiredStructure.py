"""District template `required_structures[]` item — tz_city_generation.md §9.4."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.settlement.enums.requiredStructurePosition import (
    POSITION_ANY,
    POSITION_CENTER,
    RequiredStructurePosition,
)
from app.dataModel.structure.building.buildingLayoutTemplate import DrawingKey

__all__ = [
    "POSITION_ANY",
    "POSITION_CENTER",
    "RequiredStructure",
    "RequiredStructurePosition",
]


class RequiredStructure(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    building_template: StrictOnWire[DrawingKey]
    structure_type: DefaultOnWire[str | None] = None
    count: DefaultOnWire[int] = 1
    position: DefaultOnWire[RequiredStructurePosition] = POSITION_ANY

    @field_validator("position", mode="before")
    @classmethod
    def _coerce_position(cls, value: Any) -> Any:
        if value is None:
            return None
        parsed = RequiredStructurePosition.from_wire(value)
        return parsed if parsed is not None else POSITION_ANY
