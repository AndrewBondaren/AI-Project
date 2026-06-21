"""
Doorway passage builder.
"""
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer
from app.application.worldData.generators.structure.passages.passageType import PassageType
from app.application.worldData.generators.structure.passages.shared import (
    _center_slice, _det_uuid, _shared_segment,
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

    door_cells = _center_slice(shared, width)
    mat = conn.get("frame_material") or fr.wall_material
    z = fr_level.z

    height = max(conn.get("height", passage_height), passage_height)
    placer = DoorPlacer(cells, world_uid, building_uid)
    for (x, y) in door_cells:
        placer.place(x, y, z, mat, height=height)

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
