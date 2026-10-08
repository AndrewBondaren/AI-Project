"""Authored opening parameters; placement remains algorithmic (§3.11)."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, DefaultEnumWhenMissing
from app.dataModel.locations.structure.enums.buildingElement import StructureElement, WALL_OPENING_ELEMENTS


class WallOpeningSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    opening_type: DefaultEnumWhenMissing[StructureElement | None] = None
    frame_material: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = None
    glass_material: DefaultWhenMissing[Annotated[str, Field(min_length=1)] | None] = None
    window_z: DefaultWhenMissing[Annotated[int, Field(strict=True, ge=0)] | None] = None
    _substitutions: tuple[tuple[str, str], ...] = PrivateAttr(default=())

    @field_validator("opening_type")
    @classmethod
    def _wall_opening(cls, value):
        if value is not None and value not in WALL_OPENING_ELEMENTS:
            raise ValueError("opening_type must be a wall opening element")
        return value

    @property
    def substitutions(self) -> tuple[tuple[str, str], ...]:
        return self._substitutions
