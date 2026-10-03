"""Authored opening parameters; placement remains algorithmic (§3.11)."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire
from app.dataModel.locations.structure.enums.buildingElement import StructureElement, WALL_OPENING_ELEMENTS


class WallOpeningSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    opening_type: StrictEnumOnWire[StructureElement] = None
    frame_material: DefaultOnWire[Annotated[str, Field(min_length=1)] | None] = None
    glass_material: DefaultOnWire[Annotated[str, Field(min_length=1)] | None] = None
    window_z: DefaultOnWire[Annotated[int, Field(strict=True, ge=0)] | None] = None
    _substitutions: tuple[tuple[str, str], ...] = PrivateAttr(default=())

    @model_validator(mode="wrap")
    @classmethod
    def _fallback(cls, value, handler):
        substitutions = []
        if isinstance(value, dict):
            value = dict(value)
            raw = value.get("opening_type")
            if raw is None:
                # None is the auto-resolve sentinel, despite the enum wire policy.
                value.pop("opening_type", None)
            elif not isinstance(raw, str) or raw not in WALL_OPENING_ELEMENTS:
                substitutions.append(("opening_type", repr(raw)))
                value.pop("opening_type")
        while True:
            try:
                result = handler(value)
                break
            except ValidationError as exc:
                # Degrade known parameters only; extra fields still reject.
                invalid = {error["loc"][0] for error in exc.errors()
                           if len(error["loc"]) == 1 and error["loc"][0] in cls.model_fields}
                if not isinstance(value, dict) or not invalid:
                    raise
                for name in sorted(invalid):
                    substitutions.append((name, repr(value.pop(name))))
        result._substitutions = tuple(substitutions)
        return result

    @property
    def substitutions(self) -> tuple[tuple[str, str], ...]:
        return self._substitutions
