"""
Entry-point passage builder (main entrance / service entrance).
"""
import logging
from math import floor

from app.dataModel.structure.room.entryPoint import EntryPoint
from app.dataModel.structure.building.structureTemplate import (
    DEFAULT_DOOR_HEIGHT_MAX, DEFAULT_DOOR_HEIGHT_RATIO, StructureTemplate,
)
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer
from app.application.worldData.generators.structure.passages.shared import (
    _det_uuid, _exterior_cells_on_wall,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)


def _resolve_entry_height(
    room: _RoomInstance, ep: EntryPoint, passage_height: int,
    template: StructureTemplate | None,
) -> int:
    if ep.door_height is not None:
        height = ep.door_height
    elif room.z_height <= 3:
        height = room.z_height - 1
    else:
        ratio = template.door_height_ratio if template is not None else DEFAULT_DOOR_HEIGHT_RATIO
        cap = template.door_height_max if template is not None else DEFAULT_DOOR_HEIGHT_MAX
        height = min(floor(room.z_height * ratio), cap)
    height = max(height, passage_height)
    if not passage_height <= height < room.z_height:
        uid = template.system_name if template is not None else "<unspecified>"
        raise GenerationError(
            f"Structure '{uid}', room '{room.room_id}': door_height={height} "
            f"must satisfy {passage_height} <= door_height < z_height={room.z_height}"
        )
    return height


def _build_entry_point(
    room: _RoomInstance,
    ep: EntryPoint,
    level: LocationLevel,
    all_union: set[tuple[int, int]],
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    passage_height: int,
    suffix: str = "",
    *,
    template: StructureTemplate | None = None,
) -> LocationPassage | None:
    height = _resolve_entry_height(room, ep, passage_height, template)
    facing = ep.wall
    ext_cells = _exterior_cells_on_wall(room, facing, all_union)
    if not ext_cells:
        logger.warning(
            "entry_point on room %r: no exterior wall on %r side",
            room.room_id, facing.value,
        )
        return None

    width = ep.width
    mat = ep.frame_material or room.wall_material
    z = level.z

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
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=None,
        from_x=None,
        from_y=None,
        to_level_uid=level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type=ep.passage_type,
        is_bidirectional=False,
    )
