"""
Doorway passage builder.
"""
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer
from app.application.worldData.generators.structure.passages.passageType import PassageType
from app.application.worldData.generators.structure.passages.shared import (
    _det_uuid, _doorway_facing, _shared_segment,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell


def _build_doorway(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    passage_height: int,
) -> LocationPassage | None:
    import logging
    logger = logging.getLogger(__name__)

    shared = _shared_segment(fr, to)
    if not shared:
        logger.warning("doorway %r->%r: no shared wall found", conn["from_room"], conn["to_room"])
        return None

    width = conn.get("width", 1)
    if width > len(shared):
        width = len(shared)

    mat = conn.get("frame_material") or fr.wall_material
    z = fr_level.z

    height  = max(conn.get("height", passage_height), passage_height)
    facing  = _doorway_facing(shared)
    label   = f"{conn['from_room']}->{conn['to_room']}"
    placer  = DoorPlacer(cells, world_uid, building_uid)
    valid   = placer.filter_passable_from_center(shared, z, facing)
    if not valid:
        logger.warning("doorway %r->%r: нет валидных кандидатов на стене", conn["from_room"], conn["to_room"])
        return None
    door_cells = valid[:width]
    placed  = [p for p in door_cells if placer.place(x=p[0], y=p[1], z=z, mat=mat, height=height, facing=facing, conn_label=label)]
    if not placed:
        logger.warning("doorway %r->%r: все позиции двери заблокированы", conn["from_room"], conn["to_room"])
        return None
    door_cells = placed

    cx, cy = door_cells[len(door_cells) // 2]
    passage_uid = _det_uuid(building_uid, "door", conn["from_room"], conn["to_room"])
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=cx,
        from_y=cy,
        to_level_uid=to_level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type=conn.get("passage_type", PassageType.DOORWAY),
        is_bidirectional=True,
    )
