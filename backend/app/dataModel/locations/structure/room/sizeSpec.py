"""Room size wire forms (§3.5); presets remain owned by the size registries."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire
from app.dataModel.locations.structure.enums.roomSize import RoomSize, RoomSizePreset
from app.dataModel.locations.structure.enums.staircaseSize import StaircaseSizePreset, all_staircase_size_presets

DEFAULT_EXPLICIT_Z_RANGE = (3, 3)


def _ordered_range(value: list[int]) -> list[int]:
    if value[0] < 1 or value[0] > value[1]:
        raise ValueError("range must satisfy 1 <= min <= max")
    return value


PositiveRange = Annotated[list[int], Field(min_length=2, max_length=2), AfterValidator(_ordered_range)]


class SizeSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    size_type: DefaultOnWire[str | None] = None
    width_range: DefaultOnWire[PositiveRange | None] = None
    depth_range: DefaultOnWire[PositiveRange | None] = None
    z_range: DefaultOnWire[PositiveRange | None] = None

    @model_validator(mode="after")
    def _single_form(self) -> "SizeSpec":
        if self.size_type is not None:
            if {"width_range", "depth_range"} & self.model_fields_set:
                raise ValueError("size_type excludes width_range/depth_range (§3.5)")
            if self.room_preset is None and self.staircase_preset is None:
                raise ValueError(f"unknown size_type: {self.size_type!r}")
        elif self.width_range is None:
            raise ValueError("width_range required without size_type (§3.5)")
        return self

    @property
    def room_preset(self) -> RoomSizePreset | None:
        size = RoomSize.from_size_type(self.size_type) if self.size_type else None
        return size.to_preset() if size else None

    @property
    def staircase_preset(self) -> StaircaseSizePreset | None:
        return all_staircase_size_presets().get(self.size_type)

    @property
    def resolved_width_range(self) -> list[int]:
        preset = self.staircase_preset or self.room_preset
        return list(preset.width_range) if preset else self.width_range

    @property
    def resolved_depth_range(self) -> list[int] | None:
        preset = self.staircase_preset or self.room_preset
        return list(preset.depth_range or preset.width_range) if preset else self.depth_range

    def height_range(self, level_height: int, template_height: int | None) -> list[int]:
        # Preserve staircase-size priority and template > room-preset behavior.
        if self.staircase_preset is not None:
            return [level_height, level_height]
        if self.z_range is not None:
            return self.z_range
        if template_height is not None:
            return [template_height, template_height]
        preset = self.room_preset
        return list(preset.z_range) if preset else list(DEFAULT_EXPLICIT_Z_RANGE)
