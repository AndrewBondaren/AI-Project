import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random

logger = logging.getLogger(__name__)

from app.application.worldData.generators.structure._cellBuilder import build_level_cells
from app.application.worldData.generators.structure._errors import GenerationError, UnsupportedShapeError
from app.application.worldData.generators.structure._layoutEngine import layout_level
from app.application.worldData.generators.structure._passageBuilder import build_passages
from app.application.worldData.generators.structure._roomFactory import instantiate_level_rooms
from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

__all__ = ["StructureGeneratorService", "StructureLayout", "UnsupportedShapeError", "GenerationError"]


@dataclass
class StructureLayout:
    cells:    list[MapCell]
    levels:   list[LocationLevel]
    passages: list[LocationPassage]
    rooms:    list[NamedLocation]


# ---------------------------------------------------------------------------
# Seed + z helpers

def _det_uuid(namespace: str, *parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace + "|" + "|".join(parts)))


def _make_seed(world_uid: str, building_uid: str) -> int:
    raw = (world_uid + building_uid).encode()
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def _resolve_z_heights(template: dict) -> dict[int, int]:
    """z_offset → effective z_height."""
    default = template.get("default_z_height", 3)
    return {
        level_def["z_offset"]: level_def.get("z_height") or default
        for level_def in template["levels"]
    }


def _compute_level_z(building_map_z: int, z_offset: int, z_heights: dict[int, int]) -> int:
    if z_offset == 0:
        return building_map_z
    if z_offset > 0:
        return building_map_z + sum(z_heights[k] for k in range(0, z_offset))
    return building_map_z - sum(z_heights[k] for k in range(z_offset, 0))


def _build_levels(template: dict, building: NamedLocation,
                  z_heights: dict[int, int]) -> dict[int, LocationLevel]:
    return {
        level_def["z_offset"]: LocationLevel(
            level_uid=_det_uuid(building.location_uid, f"level_{level_def['z_offset']}"),
            location_uid=building.location_uid,
            z=_compute_level_z(building.map_z, level_def["z_offset"], z_heights),
            z_height=z_heights[level_def["z_offset"]],
            display_name=level_def["display_name"],
            isolated=level_def.get("isolated", False),
            access_mechanic=level_def.get("access_mechanic", []),
        )
        for level_def in template["levels"]
    }


# ---------------------------------------------------------------------------
# Room → NamedLocation

def _room_to_named_location(
    room: _RoomInstance,
    building: NamedLocation,
    level: LocationLevel,
    room_uid: str,
) -> NamedLocation:
    return NamedLocation(
        location_uid=room_uid,
        world_uid=building.world_uid,
        display_name=room.display_name,
        system_location_type="room",
        system_location_subtype=room.room_type,
        created_at=datetime.now(timezone.utc).isoformat(),
        parent_location_uid=building.location_uid,
        is_accessible=True,
        is_discovered=False,
        is_public=room.is_public,
        is_forbidden=room.is_forbidden,
        map_x=room.origin_x,
        map_y=room.origin_y,
        map_z=level.z,
        parent_wall_material=room.wall_material,
        parent_floor_material=room.floor_material,
    )


# ---------------------------------------------------------------------------
# Service

class StructureGeneratorService:
    """
    Pure utility — no repositories, no async.
    Deterministic: same world_uid + same building_uid → same layout.
    Generates interior box: rooms, walls, passages.
    Foundation + roof + porch — StructureAssembler (layer above).
    """

    def generate_from_template(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
    ) -> StructureLayout:
        template_name = template.get("system_name", "?")
        logger.info(
            "generate_from_template | start building=%s template=%s",
            building.location_uid, template_name,
        )

        rng = Random(_make_seed(world.world_uid, building.location_uid))

        # Step 1: levels
        z_heights = _resolve_z_heights(template)
        levels    = _build_levels(template, building, z_heights)   # z_offset → LocationLevel
        logger.info("generate_from_template | levels=%s", sorted(levels))

        # Step 2–3: instantiate rooms per level
        all_rooms: list[_RoomInstance] = []
        room_z_offsets: dict[str, int] = {}   # room_id → z_offset

        for level_def in template["levels"]:
            z_offset   = level_def["z_offset"]
            level      = levels[z_offset]
            level_rooms = instantiate_level_rooms(
                level_def, template, level.z_height, z_offset, world, rng,
            )
            for room in level_rooms:
                room_z_offsets[room.room_id] = z_offset
            all_rooms.extend(level_rooms)
            logger.info(
                "generate_from_template | z_offset=%d instantiated %d rooms",
                z_offset, len(level_rooms),
            )

        # Step 4–5: layout per level
        bx = building.map_x or 0
        by = building.map_y or 0
        connections = template.get("connections", [])

        for level_def in template["levels"]:
            z_offset    = level_def["z_offset"]
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset]
            layout_level(level_rooms, connections, bx, by)
            placed = sum(1 for r in level_rooms if r.placed)
            skipped = len(level_rooms) - placed
            logger.info(
                "generate_from_template | z_offset=%d layout done: placed=%d skipped=%d",
                z_offset, placed, skipped,
            )
            if skipped:
                skipped_ids = [r.room_id for r in level_rooms if not r.placed]
                logger.warning(
                    "generate_from_template | z_offset=%d rooms not placed: %s",
                    z_offset, skipped_ids,
                )

        # Step 6–8: assign UIDs + generate cells per level
        room_uids: dict[str, str] = {}   # uid_key → location_uid
        for room in all_rooms:
            if room.placed:
                uid = _det_uuid(building.location_uid, room.uid_key)
                room_uids[room.uid_key] = uid

        cells_dict: dict[tuple, MapCell] = {}
        for level_def in template["levels"]:
            z_offset    = level_def["z_offset"]
            level       = levels[z_offset]
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
            wall_mat    = building.parent_wall_material or "stone"

            before = len(cells_dict)
            for cell in build_level_cells(
                level_rooms, connections, level.z,
                world.world_uid, building.location_uid,
                wall_mat, room_uids,
            ):
                cells_dict[(cell.x, cell.y, cell.z)] = cell
            logger.info(
                "generate_from_template | z_offset=%d cells generated: %d",
                z_offset, len(cells_dict) - before,
            )

        # Step 9–11: passages (mutates cells_dict for door/staircase cells)
        passages = build_passages(
            cells_dict, all_rooms, connections,
            levels, room_z_offsets,
            world.world_uid, building.location_uid, rng,
            world=world, template=template,
        )
        logger.info(
            "generate_from_template | passages=%d total_cells=%d",
            len(passages), len(cells_dict),
        )

        # Step 12: assemble result
        placed_rooms = [r for r in all_rooms if r.placed]
        named_locations = [
            _room_to_named_location(
                room, building,
                levels[room.z_offset],
                room_uids[room.uid_key],
            )
            for room in placed_rooms
        ]

        logger.info(
            "generate_from_template | done building=%s rooms=%d cells=%d passages=%d",
            building.location_uid, len(named_locations),
            len(cells_dict), len(passages),
        )

        return StructureLayout(
            cells=list(cells_dict.values()),
            levels=list(levels.values()),
            passages=passages,
            rooms=named_locations,
        )

    def validate_template(self, data: dict) -> list[str]:
        raise NotImplementedError
