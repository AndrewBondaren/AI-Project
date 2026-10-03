"""Conditional L/T shape parameters (§3.5b); required ranges checked by RoomDef."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, PrivateAttr, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictEnumOnWire
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing, coerce_facing_wire
from app.dataModel.structure.room.sizeSpec import PositiveRange


class ShapeParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    arm_width_range: DefaultOnWire[PositiveRange | None] = None
    arm_depth_range: DefaultOnWire[PositiveRange | None] = None
    arm_corner: DefaultOnWire[Literal["northeast", "northwest", "southeast", "southwest", "any"]] = "any"
    stem_width_range: DefaultOnWire[PositiveRange | None] = None
    stem_wall: DefaultOnWire[Literal["north", "south", "east", "west", "any"]] = "any"


class ResolvedStemWall(BaseModel):
    """Internal geometry boundary, after wire 'any' has been resolved by RNG.

    Missing/invalid cardinal preserves SOUTH and marks a diagnostic for the
    generator. This is distinct from the wire default 'any'. No RNG or logging.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    stem_wall: StrictEnumOnWire[Facing] = Facing.SOUTH
    _substituted: bool = PrivateAttr(default=False)

    @model_validator(mode="wrap")
    @classmethod
    def _cardinal_or_default(cls, value, handler):
        if not isinstance(value, dict):
            return handler(value)
        try:
            parsed = coerce_facing_wire(value.get("stem_wall"))
        except (ValueError, TypeError):
            parsed = None
        if parsed in CARDINAL_FACINGS:
            return handler({**value, "stem_wall": parsed})
        payload = dict(value)
        payload.pop("stem_wall", None)
        result = handler(payload)
        result._substituted = True
        return result

    @property
    def substituted(self) -> bool:
        return self._substituted
