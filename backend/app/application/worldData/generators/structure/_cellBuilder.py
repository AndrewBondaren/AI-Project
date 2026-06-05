"""
Cell generation — 2 passes per level.

Room coordinate model:
  Room footprints INCLUDE their 1-cell perimeter.
  Adjacent rooms share exactly ONE perimeter column/row (the interior wall).
  shared_cells = footprint_A ∩ footprint_B

Pass 2 — room floors:
  Each footprint cell → floor, location_uid = room. (base z only)
  Pass 3 will overwrite perimeter cells with walls.

Pass 3 — walls:
  Every perimeter cell (footprint minus interior) of every room → wall cell (building).
  Covers both shared perimeter between adjacent rooms AND unshared exterior perimeter.
  Because footprints include perimeter, pass 3 alone handles the full building shell —
  no extra exterior pass needed.

z_height: pass 3 walls are repeated for every z in [z_base, z_base + z_height - 1].
  Floor (Pass 2) is generated only at z_base.
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
# Pass 2

def pass2_floors(
    rooms: list[_RoomInstance],
    z: int,
    world_uid: str,
    room_uids: dict[str, str],   # uid_key → location_uid
) -> list[MapCell]:
    """
    Floor cells for ALL footprint cells of each room.
    Pass 3 will overwrite shared-perimeter cells with walls afterward.
    Exterior walls (Pass 1) are outside the footprint — no conflict.
    """
    cells: list[MapCell] = []
    for room in rooms:
        if not room.placed:
            continue
        loc_uid = room_uids[room.uid_key]
        for (x, y) in room.get_footprint():
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
    """
    Walls for every perimeter cell of every room (footprint minus interior).
    Covers both shared perimeter (between adjacent rooms) and unshared perimeter
    (outer face of a room with no neighbour on that side).
    Pass 2 placed floor at every footprint cell; this overwrites perimeter cells with wall.
    Passage builder later replaces specific wall cells with door/archway cells.
    """
    placed = [r for r in rooms if r.placed]
    seen: dict[tuple[int, int], MapCell] = {}

    for room in placed:
        fp = room.get_footprint()
        interior = _interior(fp)
        for (x, y) in fp:
            if (x, y) not in interior:
                if (x, y) not in seen:
                    seen[(x, y)] = _wall_cell(x, y, z, world_uid, building_uid, wall_material)

    return list(seen.values())


# ---------------------------------------------------------------------------
# Public entry point

def build_level_cells(
    rooms: list[_RoomInstance],
    connections: list[dict],
    z: int,
    z_height: int,
    world_uid: str,
    building_uid: str,
    wall_material: str,
    room_uids: dict[str, str],
) -> list[MapCell]:
    """
    Run all 3 passes and return combined cell list.
    Walls (Pass 1 + Pass 3) are generated for every z in [z, z + z_height - 1].
    Floor (Pass 2) is generated only at the base z.
    """
    cells: list[MapCell] = []

    # Floor only at base level
    cells.extend(pass2_floors(rooms, z, world_uid, room_uids))

    # Walls for every z in the room's full height span
    for z_layer in range(z, z + z_height):
        cells.extend(pass3_interior_walls(rooms, connections, z_layer, world_uid, building_uid, wall_material))

    return cells
