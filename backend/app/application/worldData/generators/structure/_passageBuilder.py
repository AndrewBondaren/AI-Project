"""
Passage builder — creates LocationPassage objects and places door/staircase cells.

Mutates `cells: dict[(x,y,z) → MapCell]` in-place.
Returns list[LocationPassage].

Three sources of passages:
  1. Doorway / archway connections   → door cells on shared wall + passage
  2. entry_point / back_entry_point  → door cells on exterior wall + passage (from_level=None)
  3. Staircase connections           → dispatched to staircase/_builder.py
"""
import logging
import uuid
from random import Random

from app.application.worldData.generators.structure._cellBuilder import _interior
from app.application.worldData.generators.structure._cellFactory import (
    _door_cell, _open_cell,
)
from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase._builder import build_staircase
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)

_WALL_DIRS = {"south": (0, -1), "north": (0, 1), "east": (1, 0), "west": (-1, 0)}


def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


# ---------------------------------------------------------------------------
# Shared segment helpers

def _shared_segment(r1: _RoomInstance, r2: _RoomInstance) -> list[tuple[int, int]]:
    shared = r1.get_footprint() & r2.get_footprint()
    return sorted(shared)


def _center_slice(cells: list[tuple[int, int]], width: int) -> list[tuple[int, int]]:
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
    dx, dy = _WALL_DIRS[direction]
    fp = room.get_footprint()
    result: set[tuple[int, int]] = set()
    for (x, y) in fp:
        nb = (x + dx, y + dy)
        if nb not in all_union:
            result.add((x, y))
    return sorted(result)


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
        logger.warning("doorway %r->%r: no shared wall found", conn["from_room"], conn["to_room"])
        return None

    width = conn.get("width", 1)
    if width > len(shared):
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
# 1b. Archway passages

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
            logger.warning("archway %r->%r: all shared cells blocked by third rooms",
                           conn["from_room"], conn["to_room"])
            return None

    width = conn.get("width", 2)
    if width > len(shared):
        width = len(shared)

    arch_cells = _center_slice(shared, width)
    mat = conn.get("frame_material") or fr.floor_material
    z_base = fr_level.z

    for (x, y) in arch_cells:
        for z_layer in range(z_base, z_base + fr_level.z_height):
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
# Public entry point

def build_passages(
    cells: dict[tuple, MapCell],
    rooms: list[_RoomInstance],
    connections: list[dict],
    levels: dict[int, LocationLevel],
    room_z_offsets: dict[str, int],
    world_uid: str,
    building_uid: str,
    rng: Random,
    world: World | None = None,
    template: dict | None = None,
    building_tier: str | None = None,
) -> list[LocationPassage]:
    logger.info("=== PHASE: build_passages ===")
    passages: list[LocationPassage] = []

    placed_by_id: dict[str, list[_RoomInstance]] = {}
    for r in rooms:
        if r.placed:
            placed_by_id.setdefault(r.room_id, []).append(r)

    all_union: set[tuple[int, int]] = set()
    for r in rooms:
        if r.placed:
            all_union |= r.get_footprint()

    level_unions: dict[int, set[tuple[int, int]]] = {}
    for r in rooms:
        if r.placed:
            z = room_z_offsets[r.room_id]
            level_unions.setdefault(z, set())
            level_unions[z] |= r.get_footprint()

    # --- Pass 1: doorway / archway (horizontal, same-level) ---
    staircase_conns: list[dict] = []

    for conn in connections:
        ptype = conn.get("passage_type", "doorway")
        if ptype == "staircase":
            staircase_conns.append(conn)
            continue

        fr_list = placed_by_id.get(conn["from_room"], [])
        to_list = placed_by_id.get(conn["to_room"], [])
        if not fr_list or not to_list:
            continue

        fr_offset = room_z_offsets[conn["from_room"]]
        to_offset = room_z_offsets[conn["to_room"]]
        fr_level  = levels[fr_offset]
        to_level  = levels[to_offset]

        if ptype == "archway":
            same_level_rooms = [r for r in rooms if room_z_offsets.get(r.room_id) == fr_offset]
            for fr in fr_list:
                for to in to_list:
                    if fr.get_footprint() & to.get_footprint():
                        p = _build_archway(conn, fr, to, fr_level, to_level,
                                           cells, world_uid, building_uid,
                                           other_rooms=same_level_rooms)
                        if p:
                            passages.append(p)
        else:
            for fr in fr_list:
                for to in to_list:
                    if fr.get_footprint() & to.get_footprint():
                        p = _build_doorway(conn, fr, to, fr_level, to_level,
                                           cells, world_uid, building_uid)
                        if p:
                            passages.append(p)

    # --- Pass 2: staircases ---

    # New schema: iterate template["staircases"] and build per segment using shaft instances.
    if template and template.get("staircases"):
        shaft_by_id: dict[str, list[_RoomInstance]] = {}
        for r in rooms:
            if r.is_shaft and r.staircase_id:
                shaft_by_id.setdefault(r.staircase_id, []).append(r)
        for lst in shaft_by_id.values():
            lst.sort(key=lambda r: r.instance_idx)

        for sc in template["staircases"]:
            sc_id   = sc.get("staircase_id", "staircase")
            sc_type = sc.get("staircase_type", "u_shape")
            stops   = sc.get("stops", [])
            shaft_list = shaft_by_id.get(sc_id, [])

            for i in range(len(stops) - 1):
                fr_stop_id = stops[i]
                to_stop_id = stops[i + 1]
                fr_offset  = room_z_offsets.get(fr_stop_id)
                to_offset  = room_z_offsets.get(to_stop_id)
                if fr_offset is None or to_offset is None:
                    continue

                fr_room = placed_by_id.get(fr_stop_id, [None])[0]
                to_room = placed_by_id.get(to_stop_id, [None])[0]
                if not fr_room or not to_room:
                    continue

                fr_level = levels[fr_offset]
                to_level = levels[to_offset]
                mat      = sc.get("step_material") or fr_room.floor_material

                # For non-trapdoor: shaft is the stairwell pseudo-room (same XY on all levels).
                # For trapdoor: no shaft, build directly between fr_room and to_room.
                shaft_fr = shaft_list[i] if i < len(shaft_list) else None
                shaft_to = shaft_list[i + 1] if i + 1 < len(shaft_list) else None

                # Interior width of shaft along the entry wall (perpendicular to facing).
                _shaft_ref = shaft_fr or shaft_to
                if _shaft_ref is not None:
                    _facing = _shaft_ref.facing or "north"
                    _arch_width = (
                        (_shaft_ref.width - 2) if _facing in ("north", "south")
                        else (_shaft_ref.depth - 2)
                    )
                else:
                    _arch_width = 2

                # Archway on the fr_z level: shaft_fr ↔ fr_room (entry side opening at base).
                # Only for i==0: segments i>0 reuse the previous segment's to_z archway
                # (same physical wall, same shaft XY — would create a duplicate passage).
                if i == 0 and shaft_fr is not None and shaft_fr.placed:
                    arch_conn_fr = {"from_room": shaft_fr.room_id, "to_room": fr_stop_id,
                                    "width": _arch_width}
                    same_level_rooms_fr = [r for r in rooms if room_z_offsets.get(r.room_id) == fr_offset]
                    p = _build_archway(arch_conn_fr, shaft_fr, fr_room, fr_level, fr_level,
                                       cells, world_uid, building_uid,
                                       other_rooms=same_level_rooms_fr)
                    if p:
                        passages.append(p)

                # Archway on the to_z level: shaft_to ↔ to_room (entry side opening)
                if shaft_to is not None and shaft_to.placed:
                    arch_conn = {"from_room": shaft_to.room_id, "to_room": to_stop_id,
                                 "width": _arch_width}
                    same_level_rooms = [r for r in rooms if room_z_offsets.get(r.room_id) == to_offset]
                    p = _build_archway(arch_conn, shaft_to, to_room, to_level, to_level,
                                       cells, world_uid, building_uid,
                                       other_rooms=same_level_rooms)
                    if p:
                        passages.append(p)

                # Staircase cells and passage
                if shaft_fr is not None and not shaft_fr.placed:
                    logger.warning("staircase %r segment %d: shaft_fr not placed, skipping", sc_id, i)
                    continue

                p = build_staircase(
                    sc, fr_room, to_room, fr_level, to_level,
                    cells, world_uid, building_uid, mat,
                    shaft=shaft_fr,
                )
                if p:
                    passages.append(p)

    # Old schema (backward compat): connections[passage_type=staircase].
    elif staircase_conns:
        staircase_conns.sort(
            key=lambda c: min(
                room_z_offsets.get(c["from_room"], 0),
                room_z_offsets.get(c["to_room"], 0),
            )
        )
        for conn in staircase_conns:
            fr_list = placed_by_id.get(conn["from_room"], [])
            to_list = placed_by_id.get(conn["to_room"], [])
            if not fr_list or not to_list:
                continue

            fr_offset = room_z_offsets[conn["from_room"]]
            to_offset = room_z_offsets[conn["to_room"]]
            fr_level  = levels[fr_offset]
            to_level  = levels[to_offset]
            mat       = conn.get("step_material") or fr_list[0].floor_material

            p = build_staircase(
                conn, fr_list[0], to_list[0], fr_level, to_level,
                cells, world_uid, building_uid, mat,
            )
            if p:
                passages.append(p)

    # --- Entry points ---
    for room in rooms:
        if not room.placed:
            continue
        z_offset = room_z_offsets[room.room_id]
        level = levels[z_offset]
        same_level_union = level_unions.get(z_offset, all_union)

        if room.entry_point:
            p = _build_entry_point(room, room.entry_point, level,
                                   same_level_union, cells, world_uid, building_uid)
            if p:
                passages.append(p)

        if room.back_entry_point:
            p = _build_entry_point(room, room.back_entry_point, level,
                                   same_level_union, cells, world_uid, building_uid,
                                   suffix="_back")
            if p:
                passages.append(p)

    return passages
