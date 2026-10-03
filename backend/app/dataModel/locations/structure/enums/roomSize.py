"""Built-in room size presets — enum owns width/depth/z ranges (tz_building_generator.md § size)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class RoomSizePreset:
    width_range: tuple[int, int]
    depth_range: tuple[int, int]
    z_range: tuple[int, int]


@dataclass(frozen=True)
class _RoomSizeBuiltin:
    width_range: tuple[int, int]
    depth_range: tuple[int, int]
    z_range: tuple[int, int]

    def to_preset(self) -> RoomSizePreset:
        return RoomSizePreset(
            width_range=self.width_range,
            depth_range=self.depth_range,
            z_range=self.z_range,
        )


class RoomSize(Enum):
    """Wire `size.size_type` presets for structure rooms (not staircase sq_* keys)."""

    VERY_SMALL = _RoomSizeBuiltin((2, 4), (2, 4), (2, 3))
    SMALL = _RoomSizeBuiltin((4, 6), (4, 6), (3, 3))
    MEDIUM = _RoomSizeBuiltin((6, 15), (6, 15), (3, 4))
    BIG = _RoomSizeBuiltin((15, 25), (15, 25), (3, 5))
    HUGE = _RoomSizeBuiltin((20, 30), (20, 30), (5, 10))
    COLOSSAL = _RoomSizeBuiltin((20, 100), (20, 100), (7, 20))

    @property
    def size_type(self) -> str:
        return self.name.lower()

    def __str__(self) -> str:
        return self.size_type

    @classmethod
    def from_size_type(cls, key: str) -> RoomSize | None:
        norm = (key or "").strip().lower()
        for member in cls:
            if member.size_type == norm:
                return member
        return None

    def to_preset(self) -> RoomSizePreset:
        return self.value.to_preset()

    @classmethod
    def preset_map(cls) -> dict[str, RoomSizePreset]:
        return {member.size_type: member.to_preset() for member in cls}
