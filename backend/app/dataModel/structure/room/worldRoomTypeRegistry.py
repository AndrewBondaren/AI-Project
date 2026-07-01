"""Root POJO for `worlds.room_type_registry`."""

from __future__ import annotations

from pydantic import RootModel

from app.dataModel.structure.room.roomTypeEntry import RoomTypeEntry

_CANONICAL_ENTRIES: tuple[RoomTypeEntry, ...] = (
    RoomTypeEntry(system_room="entrance", glossary_ref="room_entrance"),
    RoomTypeEntry(system_room="common_hall", glossary_ref="room_common_hall"),
    RoomTypeEntry(system_room="kitchen", glossary_ref="room_kitchen"),
    RoomTypeEntry(system_room="guest_room", glossary_ref="room_guest"),
    RoomTypeEntry(system_room="cellar", glossary_ref="room_cellar"),
    RoomTypeEntry(system_room="corridor", glossary_ref="room_corridor"),
    RoomTypeEntry(system_room="balcony", glossary_ref="room_balcony"),
)


class WorldRoomTypeRegistry(RootModel[list[RoomTypeEntry]]):
    root: list[RoomTypeEntry]

    @classmethod
    def canonical_defaults(cls) -> WorldRoomTypeRegistry:
        return cls(list(_CANONICAL_ENTRIES))
