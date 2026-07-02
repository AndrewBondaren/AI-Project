"""
Wall opening placement. Implements §3.10 of tz_building_generator.md.

Algorithm per direction per room:
  1. ExteriorWallProfile (wallOpeningResolver): exterior cells + adaptive corner cut
  2. Exclude doors ±1 → gaps
  3. split_by_gaps → segments
  4. Zone-center placement: count = max(1, len//3), pos[i] = floor((i+0.5)*len/count)
  5. Z via MiddleCellZAdjuster
"""
import logging
import math
from random import Random

from app.application.worldData.generators.utils.facing import Facing
from app.application.worldData.generators.structure.cellFactory import _opening_cell
from app.application.worldData.generators.utils.materialResolver import resolve_material
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.wallOpeningResolver import (
    ExteriorWallProfile,
    compute_exterior_wall_profiles,
)
from app.application.worldData.generators.structure.passages.wallZAdjuster import ZADJUSTER_BY_TYPE
from app.dataModel.structure.enums.buildingElement import (
    DOOR_BUILDING_ELEMENTS,
    StructureElement,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)

# Engine default: opening element → material_registry use_type for glass resolve (OQ-3).
# Candidate for dataModel when wall_openings / room_type rules expand (OQ-17+).
_GLASS_USE_TYPE: dict[StructureElement, str | None] = {
    StructureElement.WINDOW:     "window_glass",
    StructureElement.PORTHOLE:   "porthole_glass",
    StructureElement.VENT:       "vent_mesh",
    StructureElement.ARROW_SLIT: None,
}


def _split_by_gaps(cells: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    if not cells:
        return []
    segments: list[list[tuple[int, int]]] = []
    current = [cells[0]]
    for prev, curr in zip(cells, cells[1:]):
        if abs(curr[0] - prev[0]) + abs(curr[1] - prev[1]) == 1:
            current.append(curr)
        else:
            segments.append(current)
            current = [curr]
    segments.append(current)
    return segments


def _exclude_doors(
    cells: list[tuple[int, int]],
    cells_dict: dict[tuple, MapCell],
    z_base: int,
) -> list[tuple[int, int]]:
    forbidden: set[tuple[int, int]] = set()
    for i, (x, y) in enumerate(cells):
        cell = cells_dict.get((x, y, z_base))
        if cell and cell.system_building_element in DOOR_BUILDING_ELEMENTS:
            forbidden.add((x, y))
            if i > 0:
                forbidden.add(cells[i - 1])
            if i < len(cells) - 1:
                forbidden.add(cells[i + 1])
    return [c for c in cells if c not in forbidden]


def _zone_positions(
    seg: list[tuple[int, int]],
    shaft_facing: Facing | None = None,
    direction: str | None = None,
) -> list[tuple[int, int]]:
    """
    Zone-center placement (§3.10 Правило 2, step 5).
    count = max(1, len // 3).
    For shaft perpendicular walls, center index depends on which end is missing:
      facing=SOUTH + E/W wall (high-y absent) → n//2
      facing=WEST  + N/S wall (high-x absent) → n//2
      facing=NORTH + E/W wall (low-y absent)  → (n-1)//2
      facing=EAST  + N/S wall (low-x absent)  → (n-1)//2
    Multi window: floor((i + 0.5) * n / count).
    """
    n = len(seg)
    count = max(1, n // 3)
    if count == 1:
        idx = (n - 1) // 2
        if shaft_facing is not None and direction is not None:
            if shaft_facing == Facing.SOUTH and direction in (Facing.EAST, Facing.WEST):
                idx = n // 2
            elif shaft_facing == Facing.WEST and direction in (Facing.NORTH, Facing.SOUTH):
                idx = n // 2
            elif shaft_facing == Facing.NORTH and direction in (Facing.EAST, Facing.WEST):
                idx = (n - 1) // 2
            elif shaft_facing == Facing.EAST and direction in (Facing.NORTH, Facing.SOUTH):
                idx = (n - 1) // 2
        return [seg[idx]]
    return [seg[min(math.floor((i + 0.5) * n / count), n - 1)] for i in range(count)]


def place_wall_openings(
    rooms: list[_RoomInstance],
    all_fp: set[tuple[int, int]],
    cells_dict: dict[tuple, MapCell],
    level: LocationLevel,
    world: World,
    building_uid: str,
    rng: Random,
    ground_z: int = 0,
    building_tier: str | None = None,
) -> None:
    # §3.11: underground levels get no openings
    if level.z < ground_z:
        return

    occupied_xy = all_fp | {
        (x, y)
        for (x, y, z), cell in cells_dict.items()
        if z == level.z and cell.system_building_element != StructureElement.WALL
    }
    profiles = compute_exterior_wall_profiles(rooms, occupied_xy, level.z)
    logger.info("wall_openings | z=%d  rooms=%d", level.z, len(rooms))

    for room in rooms:
        profile = profiles.get(room.uid_key)
        if not profile or not profile.has_exterior_walls:
            continue

        # OQ-17: opening_type per room_type — default window
        element = StructureElement.WINDOW

        glass_use = _GLASS_USE_TYPE.get(element)
        glass_tier = TierResolver.resolve(
            world=world,
            room_tier=room.economic_tier,
            building_tier=building_tier,
            rng=rng,
        )
        glass_mat = (
            resolve_material(world, glass_use, glass_tier, rng, glass_use)
            if glass_use else None
        )

        zadjuster = ZADJUSTER_BY_TYPE[element]
        z_list = zadjuster.resolve(level.z, profile.z_height)

        shaft_facing = room.facing if room.is_shaft else None
        placed = 0
        for direction, wall_cells in profile.walls.items():
            available = _exclude_doors(wall_cells, cells_dict, level.z)
            for seg in _split_by_gaps(available):
                for (x, y) in _zone_positions(seg, shaft_facing=shaft_facing, direction=direction):
                    for abs_z in z_list:
                        existing = cells_dict.get((x, y, abs_z))
                        if not existing or existing.system_building_element != StructureElement.WALL:
                            continue
                        cells_dict[(x, y, abs_z)] = _opening_cell(
                            x, y, abs_z, world.world_uid, building_uid,
                            element.value, room.wall_material,
                            glass_material=glass_mat,
                            system_facing=direction,
                        )
                        placed += 1

        logger.info(
            "wall_openings | room=%-20s element=%-10s z=%s placed=%d",
            room.room_id, element.value, z_list, placed,
        )
