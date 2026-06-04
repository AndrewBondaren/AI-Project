"""
Passage builder — creates LocationPassage objects and places door/staircase cells.

Mutates `cells: dict[(x,y,z) → MapCell]` in-place (replaces wall → door/staircase).
Returns list[LocationPassage].

Three sources of passages:
  1. Doorway / archway connections   → door cells on shared wall + passage
  2. entry_point / back_entry_point  → door cells on exterior wall + passage (from_level=None)
  3. Staircase connections           → staircase cell(s) in each room + cross-level passage
"""
import logging
import uuid
from random import Random

from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell

logger = logging.getLogger(__name__)

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_WALL_DIRS  = {"south": (0, -1), "north": (0, 1), "east": (1, 0), "west": (-1, 0)}


def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


def _door_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
               material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="door",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _stair_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
                material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="staircase",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


# ---------------------------------------------------------------------------
# Shared segment helpers

def _shared_segment(r1: _RoomInstance, r2: _RoomInstance) -> list[tuple[int, int]]:
    """Sorted list of cells in both footprints (the shared perimeter)."""
    shared = r1.get_footprint() & r2.get_footprint()
    return sorted(shared)


def _center_slice(cells: list[tuple[int, int]], width: int) -> list[tuple[int, int]]:
    """Return `width` cells centred in the sorted segment."""
    n = len(cells)
    if width >= n:
        return cells
    mid = n // 2
    half = width // 2
    start = mid - half
    return cells[start: start + width]


# ---------------------------------------------------------------------------
# Exterior wall direction helpers

def _exterior_cells_on_wall(
    room: _RoomInstance,
    direction: str,
    all_union: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """
    Cells just outside the room footprint in `direction` that are not in any room.
    These are the exterior wall cells on that side.
    """
    dx, dy = _WALL_DIRS[direction]
    fp = room.get_footprint()
    result: set[tuple[int, int]] = set()
    for (x, y) in fp:
        nb = (x + dx, y + dy)
        if nb not in all_union:
            result.add(nb)
    return sorted(result)


def _room_by_id(rooms: list[_RoomInstance], room_id: str) -> _RoomInstance | None:
    for r in rooms:
        if r.room_id == room_id:
            return r
    return None


# ---------------------------------------------------------------------------
# 1. Doorway passages

def _build_doorway(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
) -> LocationPassage | None:
    shared = _shared_segment(fr, to)
    if not shared:
        logger.warning("doorway %r→%r: no shared wall found", conn["from_room"], conn["to_room"])
        return None

    width = conn.get("width", 1)
    if width > len(shared):
        logger.warning("doorway %r→%r: width %d > shared %d — clamped",
                       conn["from_room"], conn["to_room"], width, len(shared))
        width = len(shared)

    door_cells = _center_slice(shared, width)
    mat = conn.get("frame_material") or fr.wall_material
    z = fr_level.z

    for (x, y) in door_cells:
        cells[(x, y, z)] = _door_cell(x, y, z, world_uid, building_uid, mat)

    cx, cy = door_cells[len(door_cells) // 2]
    passage_uid = _det_uuid(building_uid, "door", conn["from_room"], conn["to_room"])
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=cx,
        from_y=cy,
        to_level_uid=to_level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type=conn.get("passage_type", "doorway"),
        is_bidirectional=True,
    )


# ---------------------------------------------------------------------------
# 2. Entry point passages

def _build_entry_point(
    room: _RoomInstance,
    ep: dict,
    level: LocationLevel,
    all_union: set[tuple[int, int]],
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    suffix: str = "",
) -> LocationPassage | None:
    direction = ep.get("wall", "south")
    ext_cells = _exterior_cells_on_wall(room, direction, all_union)
    if not ext_cells:
        logger.warning("entry_point on room %r: no exterior wall on %r side",
                       room.room_id, direction)
        return None

    width = ep.get("width", 1)
    door_cells = _center_slice(ext_cells, width)
    mat = ep.get("frame_material") or room.wall_material
    z = level.z

    for (x, y) in door_cells:
        cells[(x, y, z)] = _door_cell(x, y, z, world_uid, building_uid, mat)

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
        system_passage_type=ep.get("passage_type", "main_entrance"),
        is_bidirectional=False,
    )


# ---------------------------------------------------------------------------
# 3. Staircase passages

def _stair_position(room: _RoomInstance, position: str | None, rng: Random) -> tuple[int, int]:
    """
    Return (x, y) for staircase cell inside the room.
    Uses room footprint interior cells — picks one based on position hint.
    """
    from app.application.worldData.generators.structure._cellBuilder import _interior

    interior = list(_interior(room.get_footprint()))
    if not interior:
        # Fallback: any footprint cell
        interior = list(room.get_footprint())

    pos = position or ("center" if room.room_type in ("common_hall", "hall") else "edge")

    if pos == "center":
        xs = [x for (x, _) in interior]
        ys = [y for (_, y) in interior]
        cx = (min(xs) + max(xs)) // 2
        cy = (min(ys) + max(ys)) // 2
        # Find closest interior cell to center
        return min(interior, key=lambda p: abs(p[0] - cx) + abs(p[1] - cy))

    if pos in ("east", "northeast", "southeast"):
        max_x = max(x for (x, _) in interior)
        candidates = [(x, y) for (x, y) in interior if x == max_x]
    elif pos in ("west", "northwest", "southwest"):
        min_x = min(x for (x, _) in interior)
        candidates = [(x, y) for (x, y) in interior if x == min_x]
    elif pos == "north":
        max_y = max(y for (_, y) in interior)
        candidates = [(x, y) for (x, y) in interior if y == max_y]
    elif pos == "south":
        min_y = min(y for (_, y) in interior)
        candidates = [(x, y) for (x, y) in interior if y == min_y]
    else:  # "edge" or unknown
        edge = rng.choice(["east", "west"])
        if edge == "east":
            max_x = max(x for (x, _) in interior)
            candidates = [(x, y) for (x, y) in interior if x == max_x]
        else:
            min_x = min(x for (x, _) in interior)
            candidates = [(x, y) for (x, y) in interior if x == min_x]

    return rng.choice(candidates) if candidates else rng.choice(interior)


def _build_staircase(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    rng: Random,
) -> LocationPassage | None:
    pos_hint = conn.get("position")
    mat = conn.get("step_material") or fr.floor_material

    to_pos  = _stair_position(to, pos_hint, rng)
    fr_pos  = _stair_position(fr, None, rng)

    tx, ty = to_pos
    fx, fy = fr_pos

    cells[(fx, fy, fr_level.z)] = _stair_cell(fx, fy, fr_level.z, world_uid, building_uid, mat)
    cells[(tx, ty, to_level.z)] = _stair_cell(tx, ty, to_level.z, world_uid, building_uid, mat)

    passage_uid = _det_uuid(building_uid, "stair", conn["from_room"], conn["to_room"])
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=fx,
        from_y=fy,
        to_level_uid=to_level.level_uid,
        to_x=tx,
        to_y=ty,
        system_passage_type="staircase",
        is_bidirectional=True,
    )


# ---------------------------------------------------------------------------
# Public entry point

def build_passages(
    cells: dict[tuple, MapCell],
    rooms: list[_RoomInstance],
    connections: list[dict],
    levels: dict[int, LocationLevel],       # z_offset → LocationLevel
    room_z_offsets: dict[str, int],         # room_id → z_offset
    world_uid: str,
    building_uid: str,
    rng: Random,
) -> list[LocationPassage]:
    passages: list[LocationPassage] = []
    placed = {r.room_id: r for r in rooms if r.placed}
    all_union: set[tuple[int, int]] = set()
    for r in rooms:
        if r.placed:
            all_union |= r.get_footprint()

    # --- doorway / staircase connections ---
    for conn in connections:
        fr = placed.get(conn["from_room"])
        to = placed.get(conn["to_room"])
        if fr is None or to is None:
            continue  # one room skipped during layout

        fr_offset = room_z_offsets[conn["from_room"]]
        to_offset = room_z_offsets[conn["to_room"]]
        fr_level  = levels[fr_offset]
        to_level  = levels[to_offset]

        ptype = conn.get("passage_type", "doorway")

        if ptype == "staircase":
            p = _build_staircase(conn, fr, to, fr_level, to_level,
                                 cells, world_uid, building_uid, rng)
        else:
            p = _build_doorway(conn, fr, to, fr_level, to_level,
                               cells, world_uid, building_uid)

        if p:
            passages.append(p)

    # --- entry points ---
    for room in rooms:
        if not room.placed:
            continue
        z_offset = room_z_offsets[room.room_id]
        level = levels[z_offset]

        if room.entry_point:
            p = _build_entry_point(room, room.entry_point, level,
                                   all_union, cells, world_uid, building_uid)
            if p:
                passages.append(p)

        if room.back_entry_point:
            p = _build_entry_point(room, room.back_entry_point, level,
                                   all_union, cells, world_uid, building_uid, suffix="_back")
            if p:
                passages.append(p)

    return passages
