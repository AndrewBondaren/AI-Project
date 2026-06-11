"""
Main passage orchestrator.

Builds all passages for a structure:
  1. Doorway / archway (horizontal, same-level)
  2. Staircase segments (vertical, dispatched to staircase/_builder.py)
  3. Entry points (exterior doors)
"""
import logging
from random import Random

from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.passages.archway import _build_archway
from app.application.worldData.generators.structure.passages.doorway import _build_doorway
from app.application.worldData.generators.structure.passages.entry import _build_entry_point
from app.application.worldData.generators.structure.staircase.builder import build_staircase
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)


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

                # Archway on fr_z level: shaft_fr ↔ fr_room (only for i==0).
                # Segments i>0 reuse the previous segment's to_z archway.
                if i == 0 and shaft_fr is not None and shaft_fr.placed:
                    arch_conn_fr = {"from_room": shaft_fr.room_id, "to_room": fr_stop_id,
                                    "width": _arch_width}
                    same_level_rooms_fr = [r for r in rooms
                                           if room_z_offsets.get(r.room_id) == fr_offset]
                    p = _build_archway(arch_conn_fr, shaft_fr, fr_room, fr_level, fr_level,
                                       cells, world_uid, building_uid,
                                       other_rooms=same_level_rooms_fr)
                    if p:
                        passages.append(p)

                # Archway on to_z level: shaft_to ↔ to_room.
                if shaft_to is not None and shaft_to.placed:
                    arch_conn = {"from_room": shaft_to.room_id, "to_room": to_stop_id,
                                 "width": _arch_width}
                    same_level_rooms = [r for r in rooms
                                        if room_z_offsets.get(r.room_id) == to_offset]
                    p = _build_archway(arch_conn, shaft_to, to_room, to_level, to_level,
                                       cells, world_uid, building_uid,
                                       other_rooms=same_level_rooms)
                    if p:
                        passages.append(p)

                if shaft_fr is not None and not shaft_fr.placed:
                    logger.warning("staircase %r segment %d: shaft_fr not placed, skipping",
                                   sc_id, i)
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
