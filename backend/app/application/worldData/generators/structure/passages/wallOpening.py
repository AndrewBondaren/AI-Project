"""
Wall openings: windows, arrow slits, portholes, vents, etc.

Called after passages are built — needs door positions to exclude ±1 around them.
Replaces wall cells with opening cells at window_z height in cells_dict (in-place).

glass_material and cell_states (closed/open/broken) — v2.
Arc-length distribution for circular rooms — v2.
Interior window conflict resolution — v2 (last-write-wins for now).
"""
import logging
import math
from random import Random

from app.application.worldData.generators.structure.cellFactory import _opening_cell
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.structureElement import (
    StructureElement, _WALL_OPENING_TYPES,
)
from app.application.worldData.generators.structure.passages.wallDistributor import (
    DISTRIBUTOR_BY_TYPE,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)

_DIR_DELTA: dict[str, tuple[int, int]] = {
    "north": (0, +1),
    "south": (0, -1),
    "east":  (+1, 0),
    "west":  (-1, 0),
}

_DOOR_ELEMENTS = frozenset({"door", "archway"})


# ---------------------------------------------------------------------------
# window_z resolver

def resolve_window_z(level_def: dict, template: dict, z_height: int) -> int:
    if level_def.get("window_z_offset") is not None:
        return level_def["window_z_offset"]
    ratio = (
        level_def.get("window_z_ratio")
        or template.get("window_z_ratio")
        or 0.4
    )
    return math.floor(z_height * ratio)


# ---------------------------------------------------------------------------
# Exterior cell selection

def _cells_for_direction(
    room: _RoomInstance,
    direction: str,
    all_fp: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    dx, dy = _DIR_DELTA[direction]
    fp = room.get_footprint()
    cells = [(x, y) for (x, y) in fp if (x + dx, y + dy) not in all_fp]
    if direction in ("north", "south"):
        cells.sort(key=lambda c: c[0])
    else:
        cells.sort(key=lambda c: c[1])
    return cells


def _get_wall_cells(
    room: _RoomInstance,
    wall: str,
    all_fp: set[tuple[int, int]],
    rng: Random,
) -> list[tuple[int, int]]:
    if wall in _DIR_DELTA:
        return _cells_for_direction(room, wall, all_fp)

    if wall == "any":
        direction = rng.choice(["north", "south", "east", "west"])
        return _cells_for_direction(room, direction, all_fp)

    if wall in ("all", "perimeter"):
        seen: set[tuple[int, int]] = set()
        result: list[tuple[int, int]] = []
        for d in ("north", "south", "east", "west"):
            for c in _cells_for_direction(room, d, all_fp):
                if c not in seen:
                    seen.add(c)
                    result.append(c)
        return result

    if wall == "interior":
        fp = room.get_footprint()
        seen2: set[tuple[int, int]] = set()
        result2: list[tuple[int, int]] = []
        for (x, y) in fp:
            for dx, dy in _DIR_DELTA.values():
                nb = (x + dx, y + dy)
                if nb in all_fp and nb not in fp and (x, y) not in seen2:
                    seen2.add((x, y))
                    result2.append((x, y))
        return result2

    logger.warning("wall_openings: unknown wall=%r on room %r — skipping", wall, room.room_id)
    return []


# ---------------------------------------------------------------------------
# Available cell filtering

def _exclude_corners(cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Remove 2 cells from each end (corner ±1 exclusion per ТЗ)."""
    if len(cells) <= 4:
        return []
    return cells[2:-2]


def _exclude_doors(
    cells: list[tuple[int, int]],
    cells_dict: dict[tuple, MapCell],
    z_base: int,
) -> list[tuple[int, int]]:
    """Remove cells ±1 around any door/archway at the base z of this level."""
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


def _resolve_count(opening: dict, rng: Random) -> int:
    if "count" in opening:
        return opening["count"]
    cr = opening["count_range"]
    return rng.randint(cr[0], cr[1])


# ---------------------------------------------------------------------------
# Public entry point

def place_wall_openings(
    rooms: list[_RoomInstance],
    cells_dict: dict[tuple, MapCell],
    level: LocationLevel,
    level_def: dict,
    template: dict,
    world_uid: str,
    building_uid: str,
    rng: Random,
) -> None:
    rooms_with_openings = [r for r in rooms if r.wall_openings]
    if not rooms_with_openings:
        return

    all_fp: set[tuple[int, int]] = set()
    for r in rooms:
        all_fp |= r.get_footprint()

    window_z = resolve_window_z(level_def, template, level.z_height)
    abs_z    = level.z + window_z
    z_base   = level.z

    logger.info(
        "wall_openings | z_offset=%d  window_z=%d  abs_z=%d  rooms=%d",
        level_def["z_offset"], window_z, abs_z, len(rooms_with_openings),
    )

    for room in rooms_with_openings:
        for opening in room.wall_openings:
            raw_type = opening["opening_type"]
            try:
                element = StructureElement(raw_type)
            except ValueError:
                logger.warning(
                    "wall_openings | room=%r: unknown opening_type=%r — skipping",
                    room.room_id, raw_type,
                )
                continue
            if element not in _WALL_OPENING_TYPES:
                logger.warning(
                    "wall_openings | room=%r: opening_type=%r is not a wall opening element — skipping",
                    room.room_id, raw_type,
                )
                continue

            wall         = opening.get("wall", "perimeter")
            size         = opening.get("size", 1)
            distribution = opening.get("distribution", "evenly")
            frame_mat    = opening.get("frame_material") or room.wall_material

            wall_cells = _get_wall_cells(room, wall, all_fp, rng)
            wall_cells = _exclude_corners(wall_cells)
            wall_cells = _exclude_doors(wall_cells, cells_dict, z_base)

            if not wall_cells:
                logger.warning(
                    "wall_openings | room=%r opening_type=%r wall=%r: no available cells after filtering",
                    room.room_id, element.value, wall,
                )
                continue

            count      = _resolve_count(opening, rng)
            distributor = DISTRIBUTOR_BY_TYPE[element]
            groups     = distributor.place(wall_cells, count, size, distribution, rng)

            if not groups:
                logger.warning(
                    "wall_openings | room=%r opening_type=%r: стена слишком короткая для размещения "
                    "(available=%d, count=%d, size=%d)",
                    room.room_id, element.value, len(wall_cells), count, size,
                )
                continue

            placed = 0
            for group in groups:
                for (x, y) in group:
                    cells_dict[(x, y, abs_z)] = _opening_cell(
                        x, y, abs_z, world_uid, building_uid, element.value, frame_mat,
                    )
                    placed += 1

            logger.info(
                "wall_openings | room=%-20s opening_type=%-12s wall=%-9s placed=%d",
                room.room_id, element.value, wall, placed,
            )
