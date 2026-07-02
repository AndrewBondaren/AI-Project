"""
Entry-point passage builder (main entrance / service entrance).
"""
import logging

from app.application.worldData.generators.utils.facing import Facing
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer
from app.dataModel.structure.enums.passageType import PassageType
from app.application.worldData.generators.structure.passages.shared import (
    _DIRECTION_FACING, _det_uuid, _exterior_cells_on_wall,
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
    mat = ep.get("frame_material") or room.wall_material
    z = level.z

    height  = max(ep.get("height", passage_height), passage_height)
    facing  = _DIRECTION_FACING.get(direction, Facing.NORTH)
    label   = f"entry:{room.room_id}"
    placer  = DoorPlacer(cells, world_uid, building_uid)
    valid   = placer.filter_passable_from_center(ext_cells, z, facing, allow_exterior=True)
    if not valid:
        logger.warning("entry_point room %r: нет валидных кандидатов на стене", room.room_id)
        return None
    door_cells = valid[:width]
    placed  = [p for p in door_cells if placer.place(x=p[0], y=p[1], z=z, mat=mat, height=height, facing=facing, conn_label=label, allow_exterior=True)]
    if not placed:
        logger.warning("entry_point room %r: все позиции входа заблокированы", room.room_id)
        return None
    door_cells = placed

    cx, cy = door_cells[len(door_cells) // 2]
    passage_uid = _det_uuid(building_uid, f"entry{suffix}", room.room_id)
    passage_type = PassageType.from_wire(ep.get("passage_type"), default=PassageType.MAIN_ENTRANCE)
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=None,
        from_x=None,
        from_y=None,
        to_level_uid=level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type=passage_type,
        is_bidirectional=False,
    )
