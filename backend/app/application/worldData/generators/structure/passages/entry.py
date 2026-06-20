"""
Entry-point passage builder (main entrance / service entrance).
"""
import logging

from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer
from app.application.worldData.generators.structure.passages.shared import (
    _center_slice, _det_uuid, _exterior_cells_on_wall,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)


def _build_entry_point(
    room: _RoomInstance,
    ep: dict,
    level: LocationLevel,
    all_union: set[tuple[int, int]],
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    passage_height: int,
    suffix: str = "",
) -> LocationPassage | None:
    direction = ep.get("wall", "south")
    ext_cells = _exterior_cells_on_wall(room, direction, all_union)
    if not ext_cells:
        logger.warning(
            "entry_point on room %r: no exterior wall on %r side",
            room.room_id, direction,
        )
        return None

    width = ep.get("width", 1)
    door_cells = _center_slice(ext_cells, width)
    mat = ep.get("frame_material") or room.wall_material
    z = level.z

    height = max(ep.get("height", passage_height), passage_height)
    placer = DoorPlacer(cells, world_uid, building_uid)
    for (x, y) in door_cells:
        placer.place(x, y, z, mat, height=height)

    cx, cy = door_cells[len(door_cells) // 2]
    passage_uid = _det_uuid(building_uid, f"entry{suffix}", room.room_id)
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=None,
        from_x=None,
        from_y=None,
        to_level_uid=level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type=ep.get("passage_type", "main_entrance"),
        is_bidirectional=False,
    )
