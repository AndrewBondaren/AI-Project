"""
Shaft factory — creates _RoomInstance(is_shaft=True) from staircases[] template entries.

One _RoomInstance is created per z_offset that a shaft appears on.
For a 3-stop staircase [A, B, C], three instances are created: at z_A, z_B, z_C.
All instances of the same staircase share the same XY footprint (assigned by ShaftPlacer).

Trapdoor staircases: no shaft needed — vertical-only, no shaft footprint.
"""
import logging
from random import Random

from app.application.worldData.generators.utils.materialResolver import resolve_room_materials
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.dataModel.structure.enums.staircaseType import (
    StaircaseType,
    default_shaft_size_type,
    requires_shaft,
)
from app.application.worldData.generators.structure.staircase.uShape.uShapeHelper import (
    u_shape_march_depth,
)
from app.dataModel.structure.enums.staircaseSize import (
    default_shaft_footprint_min,
    staircase_footprint_min,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.world import World

logger = logging.getLogger(__name__)


def _resolve_shaft_size(sc_entry: dict, staircase_type: str) -> tuple[int, int]:
    size = sc_entry.get("size") or {}
    size_type = size.get("size_type")
    if size_type:
        footprint = staircase_footprint_min(size_type)
        if footprint is not None:
            return footprint
    if "width_range" in size:
        w = size["width_range"][0]
        d = size.get("depth_range", size["width_range"])[0]
        return w, d
    fallback_key = default_shaft_size_type(staircase_type)
    return staircase_footprint_min(fallback_key) or default_shaft_footprint_min()


def instantiate_shaft_rooms(
    template: dict,
    room_z_offsets: dict[str, int],
    levels: dict[int, LocationLevel],
    world: World,
    rng: Random,
    building_tier: str | None = None,
) -> list[_RoomInstance]:
    """
    Returns flat list of shaft _RoomInstances.
    Each instance has a unique room_id: 'shaft_{staircase_id}_{idx}'.
    All instances for the same staircase are identified by staircase_id prefix.
    """
    result: list[_RoomInstance] = []

    for sc in template.get("staircases", []):
        staircase_id = sc.get("staircase_id", "staircase")
        staircase_type = sc.get("staircase_type", "u_shape")
        stops = sc.get("stops", [])

        if not requires_shaft(staircase_type):
            continue

        if len(stops) < 2:
            logger.warning("shaft factory | %r: stops < 2, skipping", staircase_id)
            continue

        # Collect unique z_offsets in stops order (bottom → top)
        seen_z: set[int] = set()
        z_offsets: list[int] = []
        for stop_id in stops:
            z_off = room_z_offsets.get(stop_id)
            if z_off is None:
                logger.warning("shaft factory | %r stop=%r: unknown room, skipping", staircase_id, stop_id)
                continue
            if z_off not in seen_z:
                seen_z.add(z_off)
                z_offsets.append(z_off)

        if len(z_offsets) < 2:
            logger.warning("shaft factory | %r: fewer than 2 valid z_offsets, skipping", staircase_id)
            continue

        # Validate: shaft size must handle max z_height across all segments
        width, depth = _resolve_shaft_size(sc, staircase_type)
        shape_type = "square" if width == depth else "rectangle"

        max_z_height = 0
        for i in range(len(z_offsets) - 1):
            lv_fr = levels.get(z_offsets[i])
            lv_to = levels.get(z_offsets[i + 1])
            if lv_fr and lv_to:
                seg_z_height = abs(lv_to.z - lv_fr.z)
                max_z_height = max(max_z_height, seg_z_height)

        if staircase_type == StaircaseType.U_SHAPE:
            march_depth = u_shape_march_depth(depth)
            if march_depth < 1:
                logger.error(
                    "shaft factory | %r: shaft depth=%d gives march_depth=%d < 1 for u_shape",
                    staircase_id, depth, march_depth,
                )

        wall_mat, floor_mat = resolve_room_materials(
            world, None, None, rng, room_id=staircase_id,
            building_tier=building_tier, template=template,
        )

        for idx, z_off in enumerate(z_offsets):
            level = levels.get(z_off)
            z_height = level.z_height if level else 3
            room_id = f"shaft_{staircase_id}_{idx}"
            result.append(_RoomInstance(
                room_id=room_id,
                instance_idx=idx,
                z_offset=z_off,
                shape_type=shape_type,
                width=width,
                depth=depth,
                z_height=z_height,
                display_name=f"Шахта {staircase_id}",
                room_type="stairwell",
                is_public=False,
                is_forbidden=False,
                required=True,
                wall_material=wall_mat,
                floor_material=floor_mat,
                staircase_type=staircase_type,
                facing=sc.get("facing"),
                is_shaft=True,
                staircase_id=staircase_id,
            ))
            logger.info(
                "shaft factory | %r idx=%d z_offset=%d size=%dx%d max_z_height=%d",
                staircase_id, idx, z_off, width, depth, max_z_height,
            )

    return result
