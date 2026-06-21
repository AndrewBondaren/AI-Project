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

from app.application.worldData.generators.structure.cellFactory import _opening_cell
from app.application.worldData.generators.structure.materialResolver import resolve_material
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.wallOpeningResolver import (
    ExteriorWallProfile,
    compute_exterior_wall_profiles,
)
from app.application.worldData.generators.structure.passages.wallZAdjuster import ZADJUSTER_BY_TYPE
from app.application.worldData.generators.structure.structureElement import (
    StructureElement, _DOOR_ELEMENTS,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)

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
        if cell and cell.system_building_element in _DOOR_ELEMENTS:
            forbidden.add((x, y))
            if i > 0:
                forbidden.add(cells[i - 1])
            if i < len(cells) - 1:
                forbidden.add(cells[i + 1])
    return [c for c in cells if c not in forbidden]


def _zone_positions(seg: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Zone-center placement (§3.10 Правило 2, step 5).
    count = max(1, len // 3)
    pos[i] = floor((i + 0.5) * len / count)
    """
    n = len(seg)
    count = max(1, n // 3)
    return [seg[min(math.floor((i + 0.5) * n / count), n - 1)] for i in range(count)]


def place_wall_openings(
    rooms: list[_RoomInstance],
    all_fp: set[tuple[int, int]],
    cells_dict: dict[tuple, MapCell],
    level: LocationLevel,
    world: World,
    building_uid: str,
    rng: Random,
) -> None:
    # §3.11: underground levels get no openings
    if level.z < 0:
        return

    profiles = compute_exterior_wall_profiles(rooms, all_fp, level.z)
    logger.info("wall_openings | z=%d  rooms=%d", level.z, len(rooms))

    for room in rooms:
        profile = profiles.get(room.uid_key)
        if not profile or not profile.has_exterior_walls:
            continue

        # OQ-17: opening_type per room_type — default window
        element = StructureElement.WINDOW

        glass_use = _GLASS_USE_TYPE.get(element)
        glass_mat = (
            resolve_material(world, glass_use, room.economic_tier, rng, glass_use)
            if glass_use else None
        )

        zadjuster = ZADJUSTER_BY_TYPE[element]
        z_list = zadjuster.resolve(level.z, profile.z_height)

        placed = 0
        for direction, wall_cells in profile.walls.items():
            available = _exclude_doors(wall_cells, cells_dict, level.z)
            for seg in _split_by_gaps(available):
                for (x, y) in _zone_positions(seg):
                    for abs_z in z_list:
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
