"""
Archway passage builder.

Rule: arch frame starts one z-level above the floor (z_base + 1).
The cell at z_base is a passable floor cell (arch threshold).
"""
import logging

from app.application.worldData.generators.structure.cellFactory import (
    _floor_cell, _open_cell,
)
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.shared import (
    _center_slice, _det_uuid, _shared_segment,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)


def _build_archway(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    other_rooms: list | None = None,
) -> LocationPassage | None:
    shared = _shared_segment(fr, to)
    if not shared:
        logger.warning("archway %r->%r: no shared wall found", conn["from_room"], conn["to_room"])
        return None

    if other_rooms:
        third_fp: set[tuple[int, int]] = set()
        for r in other_rooms:
            if r is not fr and r is not to and r.placed:
                third_fp |= r.get_footprint()
        shared = [(x, y) for (x, y) in shared if (x, y) not in third_fp]
        if not shared:
            logger.warning(
                "archway %r->%r: all shared cells blocked by third rooms",
                conn["from_room"], conn["to_room"],
            )
            return None

    width = conn.get("width", 2)
    if width > len(shared):
        width = len(shared)

    arch_cells = _center_slice(shared, width)
    mat = conn.get("frame_material") or fr.floor_material
    z_base = fr_level.z

    for (x, y) in arch_cells:
        # Floor-level cell: passable threshold (arch frame starts one level above).
        cells[(x, y, z_base)] = _floor_cell(x, y, z_base, world_uid, building_uid, mat)
        for z_layer in range(z_base + 1, z_base + fr_level.z_height):
            cells[(x, y, z_layer)] = _open_cell(x, y, z_layer, world_uid, building_uid, mat)

    cx, cy = arch_cells[len(arch_cells) // 2]
    passage_uid = _det_uuid(building_uid, "arch", conn["from_room"], conn["to_room"])
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=cx,
        from_y=cy,
        to_level_uid=to_level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type="archway",
        is_bidirectional=True,
    )
