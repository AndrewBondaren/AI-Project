from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class SizePreset:
    width_range: tuple[int, int]
    depth_range: tuple[int, int]
    z_range:     tuple[int, int]


class RoomSize(str, Enum):
    VERY_SMALL = "very_small"
    SMALL      = "small"
    MEDIUM     = "medium"
    BIG        = "big"
    HUGE       = "huge"
    COLOSSAL   = "colossal"


ROOM_SIZE_PRESETS: dict[RoomSize, SizePreset] = {
    RoomSize.VERY_SMALL: SizePreset(width_range=(2,  4),   depth_range=(2,  4),   z_range=(2,  3)),
    RoomSize.SMALL:      SizePreset(width_range=(4,  6),   depth_range=(4,  6),   z_range=(3,  3)),
    RoomSize.MEDIUM:     SizePreset(width_range=(6,  15),  depth_range=(6,  15),  z_range=(3,  4)),
    RoomSize.BIG:        SizePreset(width_range=(15, 25),  depth_range=(15, 25),  z_range=(3,  5)),
    RoomSize.HUGE:       SizePreset(width_range=(20, 30),  depth_range=(20, 30),  z_range=(5,  10)),
    RoomSize.COLOSSAL:   SizePreset(width_range=(20, 100), depth_range=(20, 100), z_range=(7,  20)),
}
