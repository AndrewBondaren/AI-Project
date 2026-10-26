"""Conditional L/T shape parameters (§3.5b); required ranges checked by RoomDef."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, PrivateAttr, field_validator

from app.dataModel.annotationPolicy import DefaultWhenMissing, StrictEnumOnWire
from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing, coerce_facing_wire
from app.dataModel.locations.structure.room.sizeSpec import PositiveRange


class ShapeParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    arm_width_range: DefaultWhenMissing[PositiveRange | None] = None
    arm_depth_range: DefaultWhenMissing[PositiveRange | None] = None
    arm_corner: DefaultWhenMissing[Literal["northeast", "northwest", "southeast", "southwest", "any"]] = "any"
    stem_width_range: DefaultWhenMissing[PositiveRange | None] = None
    stem_wall: DefaultWhenMissing[Literal["north", "south", "east", "west", "any"]] = "any"


class ResolvedStemWall(BaseModel):
    """Internal geometry boundary, after wire 'any' has been resolved by RNG.

    Missing cardinal uses SOUTH; invalid supplied cardinal is rejected. This is distinct from the wire default 'any'. No RNG or logging.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    stem_wall: StrictEnumOnWire[Facing] = Facing.SOUTH
    _substituted: bool = PrivateAttr(default=False)

    @field_validator("stem_wall", mode="before")
    @classmethod
    def _cardinal(cls, value):
        parsed = coerce_facing_wire(value)
        if parsed not in CARDINAL_FACINGS:
            raise ValueError("stem_wall must be a cardinal facing")
        return parsed

    @property
    def substituted(self) -> bool:
        return self._substituted
