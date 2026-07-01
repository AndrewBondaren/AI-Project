"""Built-in staircase size presets — enums own width/depth ranges (tz_building_generator.md)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class StaircaseSizePreset:
    width_range: tuple[int, int]
    depth_range: tuple[int, int] | None = None  # None = computed from z_height


@dataclass(frozen=True)
class _StaircaseBuiltin:
    width_range: tuple[int, int]
    depth_range: tuple[int, int] | None = None

    def to_preset(self) -> StaircaseSizePreset:
        return StaircaseSizePreset(
            width_range=self.width_range,
            depth_range=self.depth_range,
        )


class StraightSize(Enum):
    """straight staircase `size.size_type` keys."""

    NARROW = _StaircaseBuiltin((3, 3))
    STANDARD = _StaircaseBuiltin((5, 5))
    WIDE = _StaircaseBuiltin((7, 7))
    LONG_NARROW = _StaircaseBuiltin((3, 3), (10, 15))
    LONG_WIDE = _StaircaseBuiltin((7, 7), (10, 15))

    @property
    def size_type(self) -> str:
        return self.name.lower()

    def __str__(self) -> str:
        return self.size_type

    @classmethod
    def from_size_type(cls, key: str) -> StraightSize | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.size_type == norm:
                return member
        return None

    def to_preset(self) -> StaircaseSizePreset:
        return self.value.to_preset()

    @classmethod
    def preset_map(cls) -> dict[str, StaircaseSizePreset]:
        return {member.size_type: member.to_preset() for member in cls}


class UShapeSize(Enum):
    """u_shape staircase `size.size_type` keys."""

    RECT_NARROW = _StaircaseBuiltin((4, 4))
    RECT_STANDARD = _StaircaseBuiltin((5, 5))
    SQ_SMALL = _StaircaseBuiltin((5, 5), (5, 5))
    SQ_MEDIUM = _StaircaseBuiltin((6, 6), (6, 6))
    SQ_LARGE = _StaircaseBuiltin((7, 7), (7, 7))

    @property
    def size_type(self) -> str:
        return self.name.lower()

    def __str__(self) -> str:
        return self.size_type

    @classmethod
    def from_size_type(cls, key: str) -> UShapeSize | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.size_type == norm:
                return member
        return None

    def to_preset(self) -> StaircaseSizePreset:
        return self.value.to_preset()

    @classmethod
    def preset_map(cls) -> dict[str, StaircaseSizePreset]:
        return {member.size_type: member.to_preset() for member in cls}


class SpiralSize(Enum):
    """spiral staircase `size.size_type` keys."""

    SPIRAL_3 = _StaircaseBuiltin((5, 5), (5, 5))
    SPIRAL_4 = _StaircaseBuiltin((6, 6), (6, 6))
    SPIRAL_5 = _StaircaseBuiltin((7, 7), (7, 7))

    @property
    def size_type(self) -> str:
        return self.name.lower()

    def __str__(self) -> str:
        return self.size_type

    @classmethod
    def from_size_type(cls, key: str) -> SpiralSize | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.size_type == norm:
                return member
        return None

    def to_preset(self) -> StaircaseSizePreset:
        return self.value.to_preset()

    @classmethod
    def preset_map(cls) -> dict[str, StaircaseSizePreset]:
        return {member.size_type: member.to_preset() for member in cls}


def all_staircase_size_presets() -> dict[str, StaircaseSizePreset]:
    """Merged lookup for room/shaft factories (`size_type` → preset)."""
    out: dict[str, StaircaseSizePreset] = {}
    for enum_cls in (StraightSize, UShapeSize, SpiralSize):
        out.update(enum_cls.preset_map())
    return out


STRAIGHT_SIZE_PRESETS: dict[StraightSize, StaircaseSizePreset] = {
    member: member.to_preset() for member in StraightSize
}
USHAPE_SIZE_PRESETS: dict[UShapeSize, StaircaseSizePreset] = {
    member: member.to_preset() for member in UShapeSize
}
SPIRAL_SIZE_PRESETS: dict[SpiralSize, StaircaseSizePreset] = {
    member: member.to_preset() for member in SpiralSize
}
