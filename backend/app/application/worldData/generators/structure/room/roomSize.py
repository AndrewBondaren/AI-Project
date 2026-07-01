"""Re-export room size contract from dataModel."""

from app.dataModel.structure.enums.roomSize import RoomSize, RoomSizePreset

# Back-compat alias used by older generator imports.
SizePreset = RoomSizePreset

ROOM_SIZE_PRESETS: dict[RoomSize, RoomSizePreset] = {
    member: member.to_preset() for member in RoomSize
}

__all__ = ["ROOM_SIZE_PRESETS", "RoomSize", "RoomSizePreset", "SizePreset"]
