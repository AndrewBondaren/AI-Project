from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class SizePreset:
    width_range: tuple[int, int]
    depth_range: tuple[int, int]
    z_range:     tuple[int, int]


class RoomSize(str, Enum):
    SMALL    = "small"
    MEDIUM   = "medium"
    BIG      = "big"
    HUGE     = "huge"
    COLOSSAL = "colossal"


ROOM_SIZE_PRESETS: dict[RoomSize, SizePreset] = {
    RoomSize.SMALL:    SizePreset(width_range=(2,  4),   depth_range=(2,  4),   z_range=(3,  3)),
    RoomSize.MEDIUM:   SizePreset(width_range=(5,  10),  depth_range=(5,  10),  z_range=(3,  3)),
    RoomSize.BIG:      SizePreset(width_range=(10, 20),  depth_range=(10, 20),  z_range=(3,  5)),
    RoomSize.HUGE:     SizePreset(width_range=(10, 20),  depth_range=(10, 20),  z_range=(5,  10)),
    RoomSize.COLOSSAL: SizePreset(width_range=(20, 100), depth_range=(20, 100), z_range=(7,  20)),
}
