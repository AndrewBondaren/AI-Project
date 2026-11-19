"""Typed identity adapters for standalone locations and generation scopes."""

from app.ids.deterministicIds import entity_uid
from app.ids.uidKind import UidKind


def _require_strings(**values: str) -> None:
    invalid = [name for name, value in values.items() if not isinstance(value, str) or not value]
    if invalid:
        raise ValueError("non-empty strings required: " + ", ".join(invalid))


def standalone_building_uid(world_uid: str, template_uid: str, map_x: int, map_y: int) -> str:
    _require_strings(world_uid=world_uid, template_uid=template_uid)
    return entity_uid(world_uid, UidKind.BUILDING, channel="standalone",
                      template=template_uid, x=map_x, y=map_y)


def debug_building_uid(world_uid: str) -> str:
    _require_strings(world_uid=world_uid)
    return entity_uid(world_uid, UidKind.BUILDING, channel="debug")


def area_scope_uid(world_uid: str, building_uid: str) -> str:
    _require_strings(world_uid=world_uid, building_uid=building_uid)
    return entity_uid(world_uid, UidKind.AREA_SCOPE, building=building_uid)


def room_scope_uid(world_uid: str, building_uid: str, room_id: str) -> str:
    _require_strings(world_uid=world_uid, building_uid=building_uid, room_id=room_id)
    return entity_uid(world_uid, UidKind.ROOM_SCOPE, building=building_uid, room=room_id)


def packing_token_uid(
    world_uid: str, settlement_uid: str | None, origin_x: int, origin_y: int,
    ground_z: int, slot_index: int, template_uid: str, copy_index: int,
) -> str:
    _require_strings(world_uid=world_uid, template_uid=template_uid,
                     **({"settlement_uid": settlement_uid} if settlement_uid is not None else {}))
    if copy_index < 0:
        raise ValueError("copy_index must be non-negative")
    return entity_uid(
        world_uid, UidKind.PACKING_TOKEN, x=origin_x, y=origin_y, z=ground_z,
        slot=slot_index, template=template_uid, copy=copy_index,
        **({"settlement": settlement_uid} if settlement_uid is not None else {}),
    )
