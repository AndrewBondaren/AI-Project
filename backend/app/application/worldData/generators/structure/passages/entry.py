"""
Entry-point passage builder (main entrance / service entrance).
"""
import logging

from app.dataModel.locations.structure.room.entryPoint import EntryPoint
from app.dataModel.spatial.facing import CARDINAL_WALL_OUTWARD_DELTA
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.application.worldData.generators.structure.passages.doorHeight import resolve_door_height
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer
from app.application.worldData.generators.structure.passages.shared import (
    _exterior_cells_on_wall,
)
from app.db.models.locationLevel import LocationLevel
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.application.worldData.generators.structure.physicalTransition import physical_transition, level_endpoint
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)


def _resolve_entry_height(
    room: _RoomInstance, ep: EntryPoint, passage_height: int,
    template: StructureTemplate | None,
) -> int:
    return resolve_door_height(
        room.z_height, ep.door_height, passage_height, template,
        context=f"room '{room.room_id}'",
    )


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
) -> Transition | None:
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
    dx, dy = CARDINAL_WALL_OUTWARD_DELTA[facing]
    source = TransitionEndpoint(x=cx + dx, y=cy + dy, z=level.z)
    return physical_transition(world_uid, ep.passage_type, source,
                               level_endpoint(level, cx, cy, building_uid), building_uid)
