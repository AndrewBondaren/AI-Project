"""
Wall openings: windows, arrow slits, portholes, vents, etc.

Called after passages are built — needs door positions to exclude ±1 around them.
Replaces wall cells with opening cells at window_z height in cells_dict (in-place).

cell_states (closed/open/broken) — v2.
Arc-length distribution for circular rooms — v2.
Interior window conflict resolution — v2 (last-write-wins for now).
"""
import logging
from random import Random

from app.application.worldData.generators.structure.cellFactory import _opening_cell
from app.application.worldData.generators.structure.materialResolver import resolve_material
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.facing import Facing
from app.application.worldData.generators.structure.structureElement import (
    StructureElement, _WALL_OPENING_TYPES, _DOOR_ELEMENTS,
)
from app.application.worldData.generators.structure.passages.wallDistributor import (
    DISTRIBUTOR_BY_TYPE,
    DISTRIBUTOR_BY_DISTRIBUTION,
)
from app.application.worldData.generators.structure.passages.wallZAdjuster import (
    ZADJUSTER_BY_TYPE,
)
from app.db.models.locationLevel import LocationLevel
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)

# use_type keys for resolve_material; None = no filling (open slit)
_GLASS_USE_TYPE: dict[StructureElement, str | None] = {
    StructureElement.WINDOW:     "window_glass",
    StructureElement.PORTHOLE:   "porthole_glass",
    StructureElement.VENT:       "vent_mesh",
    StructureElement.ARROW_SLIT: None,
}

_DIR_DELTA: dict[Facing, tuple[int, int]] = {
    Facing.NORTH: (0, +1),
    Facing.SOUTH: (0, -1),
    Facing.EAST:  (+1, 0),
    Facing.WEST:  (-1, 0),
}


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
) -> tuple[list[tuple[int, int]], dict[tuple[int, int], str]]:
    """Return (cells, facings) where facings maps each cell to the cardinal direction it faces outward."""
    if wall in _DIR_DELTA:
        cells = _cells_for_direction(room, wall, all_fp)
        return cells, {c: wall for c in cells}

    if wall == "any":
        direction = rng.choice(["north", "south", "east", "west"])
        cells = _cells_for_direction(room, direction, all_fp)
        return cells, {c: direction for c in cells}

    if wall in ("all", "perimeter"):
        seen: set[tuple[int, int]] = set()
        result: list[tuple[int, int]] = []
        facings: dict[tuple[int, int], str] = {}
        for d in ("north", "south", "east", "west"):
            for c in _cells_for_direction(room, d, all_fp):
                if c not in seen:
                    seen.add(c)
                    result.append(c)
                    facings[c] = d
        return result, facings

    if wall == "interior":
        fp = room.get_footprint()
        seen2: set[tuple[int, int]] = set()
        result2: list[tuple[int, int]] = []
        facings2: dict[tuple[int, int], str] = {}
        for (x, y) in fp:
            for dir_name, (dx, dy) in _DIR_DELTA.items():
                nb = (x + dx, y + dy)
                if nb in all_fp and nb not in fp and (x, y) not in seen2:
                    seen2.add((x, y))
                    result2.append((x, y))
                    facings2[(x, y)] = dir_name
                    break
        return result2, facings2

    logger.warning("wall_openings: unknown wall=%r on room %r — skipping", wall, room.room_id)
    return [], {}


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


def _resolve_count(opening: dict) -> tuple[int, int]:
    """Return (target_count, min_count). target = max to attempt; min = threshold below which we skip."""
    if "count" in opening:
        n = opening["count"]
        return n, n
    cr = opening["count_range"]
    return cr[1], cr[0]


# ---------------------------------------------------------------------------
# Public entry point

def place_wall_openings(
    rooms: list[_RoomInstance],
    cells_dict: dict[tuple, MapCell],
    level: LocationLevel,
    level_def: dict,
    world: World,
    building_uid: str,
    rng: Random,
) -> None:
    rooms_with_openings = [r for r in rooms if r.wall_openings]
    if not rooms_with_openings:
        return

    all_fp: set[tuple[int, int]] = set()
    for r in rooms:
        all_fp |= r.get_footprint()

    z_base    = level.z
    world_uid = world.world_uid

    # Interior-wall conflict resolution: lex-smaller room_id claims cells first.
    # Non-interior openings are unaffected by this ordering.
    rooms_with_openings.sort(key=lambda r: r.room_id)
    interior_claimed: set[tuple[int, int]] = set()

    logger.info(
        "wall_openings | z_offset=%d  rooms=%d",
        level_def["z_offset"], len(rooms_with_openings),
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

            wall_cells, facings = _get_wall_cells(room, wall, all_fp, rng)
            wall_cells = _exclude_corners(wall_cells)
            wall_cells = _exclude_doors(wall_cells, cells_dict, z_base)
            if wall == "interior":
                wall_cells = [c for c in wall_cells if c not in interior_claimed]

            if not wall_cells:
                logger.warning(
                    "wall_openings | room=%r opening_type=%r wall=%r: no available cells after filtering",
                    room.room_id, element.value, wall,
                )
                continue

            count, min_count = _resolve_count(opening)
            distributor = (
                DISTRIBUTOR_BY_DISTRIBUTION.get(distribution)
                or DISTRIBUTOR_BY_TYPE[element]
            )
            groups      = distributor.place(wall_cells, count, size, distribution, rng)

            if len(groups) < min_count:
                logger.warning(
                    "wall_openings | room=%r opening_type=%r: стена слишком короткая для размещения "
                    "(available=%d, target=%d, min=%d, placed=%d, size=%d)",
                    room.room_id, element.value, len(wall_cells), count, min_count, len(groups), size,
                )
                continue

            zadjuster    = ZADJUSTER_BY_TYPE[element]
            z_list       = zadjuster.resolve(level.z, room.z_height)

            glass_use    = _GLASS_USE_TYPE.get(element)
            glass_mat    = (
                resolve_material(world, glass_use, room.economic_tier, rng, glass_use)
                if glass_use else None
            )

            placed = 0
            for abs_z in z_list:
                for group in groups:
                    for (x, y) in group:
                        cells_dict[(x, y, abs_z)] = _opening_cell(
                            x, y, abs_z, world_uid, building_uid, element.value, frame_mat,
                            glass_material=glass_mat,
                            system_facing=facings.get((x, y)),
                        )
                        placed += 1

            if wall == "interior":
                interior_claimed |= {(x, y) for group in groups for (x, y) in group}

            logger.info(
                "wall_openings | room=%-20s opening_type=%-12s wall=%-9s z=%s placed=%d",
                room.room_id, element.value, wall, z_list, placed,
            )
