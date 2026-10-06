"""
Doorway passage builder.
"""
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.doorPlacer import DoorPlacer
from app.dataModel.locations.structure.building.roomConnection import RoomConnection
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.application.worldData.generators.structure.passages.doorHeight import resolve_door_height
from app.application.worldData.generators.structure.passages.shared import (
    _doorway_facing, _shared_segment,
)
from app.db.models.locationLevel import LocationLevel
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.application.worldData.generators.structure.physicalTransition import physical_transition, level_endpoint
from app.db.models.mapCell import MapCell


def _build_doorway(
    conn: RoomConnection,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    passage_height: int,
    *,
    template: StructureTemplate | None = None,
) -> Transition | None:
    import logging
    logger = logging.getLogger(__name__)

    shared = _shared_segment(fr, to)
    if not shared:
        logger.warning("doorway %r->%r: no shared wall found", conn.from_room, conn.to_room)
        return None

    width = conn.width
    if width > len(shared):
        width = len(shared)

    mat = conn.frame_material or fr.wall_material
    z = fr_level.z

    height = resolve_door_height(
        min(fr.z_height, to.z_height), conn.door_height, passage_height, template,
        context=f"connection '{conn.from_room}->{conn.to_room}'",
    )
    facing  = _doorway_facing(shared)
    label   = f"{conn.from_room}->{conn.to_room}"
    placer  = DoorPlacer(cells, world_uid, building_uid)
    valid   = placer.filter_passable_from_center(shared, z, facing)
    if not valid:
        logger.warning("doorway %r->%r: нет валидных кандидатов на стене", conn.from_room, conn.to_room)
        return None
    door_cells = valid[:width]
    placed  = [p for p in door_cells if placer.place(x=p[0], y=p[1], z=z, mat=mat, height=height, facing=facing, conn_label=label)]
    if not placed:
        logger.warning("doorway %r->%r: все позиции двери заблокированы", conn.from_room, conn.to_room)
        return None
    door_cells = placed

    cx, cy = door_cells[len(door_cells) // 2]
    return physical_transition(world_uid, conn.passage_type, level_endpoint(fr_level, cx, cy, building_uid), level_endpoint(to_level, cx, cy, building_uid), building_uid)
