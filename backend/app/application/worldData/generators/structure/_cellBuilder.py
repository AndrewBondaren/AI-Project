"""
Cell generation — 3 passes per level.

Room coordinate model:
  Room footprints INCLUDE their 1-cell perimeter.
  Adjacent rooms share exactly ONE perimeter column/row (the interior wall).
  shared_cells = footprint_A ∩ footprint_B

Pass 1 — exterior walls:
  For every cell in union(all room footprints), each neighbor outside union → wall cell.
  Walls belong to building (location_uid = building_uid).

Pass 2 — room floors:
  Interior cells = room footprint cells where all 4 neighbours are also in the footprint.
  Each interior cell → floor, location_uid = room.

Pass 3 — interior walls:
  For each connected room pair: shared = fp_A ∩ fp_B → wall cells (building).
  These cells were perimeter for both rooms, so Pass 2 didn't touch them.

All cells on a level share the same z = level.z (floor plane).
z_height is stored on LocationLevel and used for window/stair calculations, not for extra z-layers.
"""
from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.db.models.mapCell import MapCell

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))


# ---------------------------------------------------------------------------
# Helpers

def _union(rooms: list[_RoomInstance]) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for r in rooms:
        result |= r.get_footprint()
    return result


def _interior(footprint: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """Cells where all 4 neighbours are also in the footprint."""
    return {
        (x, y) for (x, y) in footprint
        if all((x + dx, y + dy) in footprint for dx, dy in _NEIGHBOURS)
    }


def _wall_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
               material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="wall",
        system_material=material,
        is_structural=True,
        location_uid=building_uid,
    )


def _floor_cell(x: int, y: int, z: int, world_uid: str, room_uid: str,
                material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="floor",
        system_material=material,
        is_structural=False,
        location_uid=room_uid,
    )


# ---------------------------------------------------------------------------
# Pass 1

def pass1_exterior_walls(
    rooms: list[_RoomInstance],
    z: int,
    world_uid: str,
    building_uid: str,
    wall_material: str,
) -> list[MapCell]:
    union = _union(rooms)
    exterior: set[tuple[int, int]] = set()
    for (x, y) in union:
        for dx, dy in _NEIGHBOURS:
            nb = (x + dx, y + dy)
            if nb not in union:
                exterior.add(nb)
    return [_wall_cell(x, y, z, world_uid, building_uid, wall_material)
            for (x, y) in exterior]


# ---------------------------------------------------------------------------
# Pass 2

def pass2_floors(
    rooms: list[_RoomInstance],
    z: int,
    world_uid: str,
    room_uids: dict[str, str],   # uid_key → location_uid
) -> list[MapCell]:
    cells: list[MapCell] = []
    for room in rooms:
        if not room.placed:
            continue
        loc_uid = room_uids[room.uid_key]
        for (x, y) in _interior(room.get_footprint()):
            cells.append(_floor_cell(x, y, z, world_uid, loc_uid, room.floor_material))
    return cells


# ---------------------------------------------------------------------------
# Pass 3

def pass3_interior_walls(
    rooms: list[_RoomInstance],
    connections: list[dict],
    z: int,
    world_uid: str,
    building_uid: str,
    wall_material: str,
) -> list[MapCell]:
    placed = {r.room_id: r for r in rooms if r.placed}
    seen: dict[tuple[int, int], MapCell] = {}

    for conn in connections:
        if conn.get("passage_type") == "staircase":
            continue
        fr = placed.get(conn["from_room"])
        to = placed.get(conn["to_room"])
        if fr is None or to is None:
            continue

        shared = fr.get_footprint() & to.get_footprint()
        for (x, y) in shared:
            if (x, y) not in seen:
                seen[(x, y)] = _wall_cell(x, y, z, world_uid, building_uid, wall_material)

    return list(seen.values())


# ---------------------------------------------------------------------------
# Public entry point

def build_level_cells(
    rooms: list[_RoomInstance],
    connections: list[dict],
    z: int,
    world_uid: str,
    building_uid: str,
    wall_material: str,
    room_uids: dict[str, str],
) -> list[MapCell]:
    """Run all 3 passes and return combined cell list."""
    cells: list[MapCell] = []
    cells.extend(pass1_exterior_walls(rooms, z, world_uid, building_uid, wall_material))
    cells.extend(pass2_floors(rooms, z, world_uid, room_uids))
    cells.extend(pass3_interior_walls(rooms, connections, z, world_uid, building_uid, wall_material))
    return cells
