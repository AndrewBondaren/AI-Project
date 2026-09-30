"""Typed room boundary; StructureTemplate retains original room dictionaries."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire, StrictEnumOnWire
from app.dataModel.structure.enums.attachWall import AttachWall
from app.dataModel.structure.enums.buildingPurpose import BuildingPurpose
from app.dataModel.structure.enums.passageType import PassageType
from app.dataModel.structure.room.entryPoint import EntryPoint
from app.dataModel.structure.room.shapeParams import ShapeParams
from app.dataModel.structure.room.sizeSpec import PositiveRange, SizeSpec


class RoomDef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    room_id: StrictOnWire[str]
    display_name: StrictOnWire[str]
    room_type: StrictOnWire[str]
    is_public: StrictOnWire[bool]
    is_forbidden: StrictOnWire[bool]
    required: StrictOnWire[bool]
    size: StrictOnWire[SizeSpec]
    shape_type: DefaultOnWire[str | list[str] | None] = None
    count: DefaultOnWire[int] = Field(default=1, ge=1)
    count_range: DefaultOnWire[PositiveRange | None] = None
    economic_tier: DefaultOnWire[str | None] = None
    attach_to: DefaultOnWire[str | None] = None
    attach_wall: StrictEnumOnWire[AttachWall] = AttachWall.BOTH
    perimeter_required: DefaultOnWire[bool] = False
    underground_fallback: DefaultOnWire[bool] = False
    staircase_type: DefaultOnWire[str | None] = None
    facing: DefaultOnWire[str | None] = None
    shape_params: DefaultOnWire[ShapeParams | None] = None
    entry_point: DefaultOnWire[EntryPoint | None] = None
    back_entry_point: DefaultOnWire[EntryPoint | None] = None
    purpose: DefaultOnWire[BuildingPurpose | None] = None
    # Wire contract only; consuming these is outside the POJO migration.
    passage_type: DefaultOnWire[PassageType] = PassageType.DOORWAY
    max_overhang: DefaultOnWire[int] = Field(default=0, ge=0)
    has_column: DefaultOnWire[bool] = False
    wall_openings: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    _attach_wall_substitution: tuple[str, str] | None = PrivateAttr(default=None)

    @model_validator(mode="wrap")
    @classmethod
    def _attach_wall_fallback(cls, value, handler):
        substitution = None
        if isinstance(value, dict):
            raw = value.get("attach_wall")
            if not isinstance(raw, str) or raw not in AttachWall:
                # Missing field is meaningful only for an attached room.
                if "attach_wall" in value or value.get("attach_to") is not None:
                    substitution = ("attach_wall", repr(raw) if "attach_wall" in value else "<missing>")
                value = {**value, "attach_wall": AttachWall.BOTH}
        try:
            result = handler(value)
        except ValidationError as exc:
            room_id = value.get("room_id") if isinstance(value, dict) else None
            raise ValueError(f"room '{room_id}': {exc}") from exc
        if substitution is not None:
            result._attach_wall_substitution = substitution
        return result

    @property
    def substitutions(self) -> tuple[tuple[str, str], ...]:
        return (self._attach_wall_substitution,) if self._attach_wall_substitution else ()

    @model_validator(mode="after")
    def _conditional_fields(self) -> "RoomDef":
        if "count" in self.model_fields_set and self.count_range is not None:
            raise ValueError(f"room '{self.room_id}': count and count_range are mutually exclusive")
        if not self.required and self.count_range is None:
            raise ValueError(f"room '{self.room_id}': required=false requires count_range")
        if self.required and self.count_range is not None:
            raise ValueError(f"room '{self.room_id}': count_range requires required=false")
        shapes = self.shape_type if isinstance(self.shape_type, list) else [self.shape_type]
        if not shapes:
            raise ValueError(f"room '{self.room_id}': shape_type list must not be empty")
        if self.size.resolved_depth_range is None and any(
            shape not in ("square", "circle", "semicircle") for shape in shapes
        ):
            raise ValueError(f"room '{self.room_id}': depth_range required for this shape")
        params = self.shape_params
        if "l_shape" in shapes:
            if params is None or params.arm_width_range is None or params.arm_depth_range is None:
                raise ValueError(f"room '{self.room_id}': l_shape requires shape_params arm_width_range/arm_depth_range")
        if "t_shape" in shapes:
            if params is None or params.stem_width_range is None:
                raise ValueError(f"room '{self.room_id}': t_shape requires shape_params stem_width_range")
            if params.stem_width_range[1] >= self.size.resolved_width_range[0]:
                raise ValueError(f"room '{self.room_id}': stem_width_range[1] must be < size.width_range[0]")
        return self
