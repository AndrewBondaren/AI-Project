"""
Post-passages corridor connector.
Runs after passages (build_passages), before wall_openings.
ТЗ: docs/tz_corridor_connect.md
"""
from __future__ import annotations

import logging
from collections import deque

from app.application.worldData.generators.structure.cellBuilder import _wall_cell
from app.application.worldData.generators.structure.cellFactory import _floor_cell, _open_cell
from app.application.worldData.generators.structure.structureElement import StructureElement
from app.application.worldData.generators.facing import Facing
from app.application.worldData.generators.structure.passages.tunnelPathFinder import TunnelPathFinder
from app.application.worldData.generators.structure.passages.wallBreachPlacer import WallBreachPlacer
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel

logger = logging.getLogger(__name__)

_DIRS: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))

_VEC_TO_FACING: dict[tuple[int, int], Facing] = {
    (1,  0): Facing.EAST,
    (-1, 0): Facing.WEST,
    (0,  1): Facing.NORTH,
    (0, -1): Facing.SOUTH,
}


def connect_corridors(
    all_rooms:      list[_RoomInstance],
    cells:          dict,
    levels:         dict[int, LocationLevel],
    world_uid:      str,
    building_uid:   str,
    wall_mat:       str,
    passage_height: int,
) -> None:
    """
    For each level: find disconnected corridor pairs, build connecting tunnels.
    Mutates cells in-place.
    Cannot modify cells belonging to non-corridor rooms (walls or interiors).
    """
    for z_offset in sorted({r.z_offset for r in all_rooms if r.placed}):
        level = levels.get(z_offset)
        if level is None:
            continue

        corridors = [
            r for r in all_rooms
            if r.placed and r.z_offset == z_offset and r.room_type == "corridor"
        ]
        if len(corridors) < 2:
            continue

        z_floor  = level.z
        z_height = level.z_height

        all_level_rooms = [r for r in all_rooms if r.placed and r.z_offset == z_offset]
        all_fp: set[tuple[int, int]] = set()
        for r in all_level_rooms:
            all_fp |= r.get_footprint()

        bx_min = min(x for x, y in all_fp)
        bx_max = max(x for x, y in all_fp)
        by_min = min(y for x, y in all_fp)
        by_max = max(y for x, y in all_fp)
        bounds = (bx_min, by_min, bx_max, by_max)

        # Blocked for pathfinding = all room footprints
        # (path travels through free space outside rooms)
        blocked_base = frozenset(all_fp)

        # Cells that belong to non-corridor rooms (cannot overwrite)
        corridor_fp: set[tuple[int, int]] = set()
        for c in corridors:
            corridor_fp |= c.get_footprint()
        non_corridor_fp = all_fp - corridor_fp

        # Pre-sort pairs by minimum wall distance (closest first)
        pairs = [
            (corridors[i], corridors[j])
            for i in range(len(corridors))
            for j in range(i + 1, len(corridors))
        ]
        pairs.sort(key=lambda p: _min_wall_distance(p[0], p[1]))

        for A, B in pairs:
            if _are_connected(A, B, cells, z_floor):
                continue

            interior_w = max(1, min(A.width, A.depth) - 2)
            path = _find_path(A, B, blocked_base, bounds, interior_w, all_fp, cells, z_floor)
            if path is None:
                logger.warning(
                    "connect | z=%d  %r ↔ %r: no path found",
                    z_offset, A.room_id, B.room_id,
                )
                continue

            actual_w = _verify_width(path, interior_w, all_fp)
            _build_tunnel(
                path, cells, world_uid, building_uid, wall_mat,
                z_floor, z_height, A, B, non_corridor_fp, actual_w,
                passage_height,
            )
            logger.info(
                "connect | z=%d  %r ↔ %r: built tunnel  len=%d  w=%d",
                z_offset, A.room_id, B.room_id, len(path), actual_w,
            )


# ---------------------------------------------------------------------------
# Connectivity

def _are_connected(
    A: _RoomInstance,
    B: _RoomInstance,
    cells: dict,
    z_floor: int,
) -> bool:
    """Flood fill on non-wall cells at z_floor. Returns True if A and B share a component."""
    a_fp = A.get_footprint()
    b_fp = B.get_footprint()

    non_wall = {
        (x, y)
        for (x, y, z), cell in cells.items()
        if z == z_floor and cell.system_building_element != "wall"
    }

    start: tuple[int, int] | None = None
    for xy in a_fp:
        if xy in non_wall:
            start = xy
            break
    if start is None:
        return False

    visited: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque([start])
    visited.add(start)
    while queue:
        cx, cy = queue.popleft()
        if (cx, cy) in b_fp and (cx, cy) in non_wall:
            return True
        for dx, dy in _DIRS:
            nb = (cx + dx, cy + dy)
            if nb in non_wall and nb not in visited:
                visited.add(nb)
                queue.append(nb)
    return False


# ---------------------------------------------------------------------------
# Pathfinding

def _find_path(
    A:          _RoomInstance,
    B:          _RoomInstance,
    blocked:    frozenset[tuple[int, int]],
    bounds:     tuple[int, int, int, int],
    interior_w: int,
    all_fp:     set[tuple[int, int]],
    cells:      dict,
    z_floor:    int,
) -> list[tuple[int, int]] | None:
    """
    Try interior_w-wide path first, fallback to width=1.
    Returns the path through free space (exterior of A to exterior of B).
    """
    a_fp = A.get_footprint()
    b_fp = B.get_footprint()

    # Start candidates = free cells adjacent to A, where breach would open into A's interior
    starts = _exterior_candidates(a_fp, blocked, cells, z_floor)
    # Target = free cells adjacent to B, where breach would open into B's interior
    target = _exterior_candidates(b_fp, blocked, cells, z_floor)

    if not starts or not target:
        return None

    finder = TunnelPathFinder()
    target_set = set(target)

    # Sort starts by proximity to face end of A
    starts = _sort_by_face(starts, A)

    for start in starts:
        if start in target_set:
            continue
        path = finder.find_path(start, target_set, set(blocked), bounds)
        if len(path) >= 2:
            return path

    return None


def _exterior_candidates(
    fp:      set[tuple[int, int]],
    blocked: frozenset[tuple[int, int]],
    cells:   dict,
    z_floor: int,
) -> list[tuple[int, int]]:
    """
    Returns free cells adjacent to fp where the breach would open into a walkable interior.
    Skips candidates where the "through" cell (opposite side of the breach) is a wall.
    Skips candidates where the through-cell at z_floor+1 is an ARCHWAY (open) cell —
    this means the breach wall is already an archway threshold (e.g. staircase entry);
    the tunnel should breach a different wall cell instead.
    """
    result: set[tuple[int, int]] = set()
    for cx, cy in fp:
        for dx, dy in _DIRS:
            ex, ey = cx + dx, cy + dy   # exterior candidate (tunnel side)
            if (ex, ey) in blocked:
                continue
            # through-cell = the cell on the interior side of the breach
            tx, ty = cx - dx, cy - dy
            cell = cells.get((tx, ty, z_floor))
            if cell and cell.system_building_element == "wall":
                continue
            # If the cell above the through-cell is an archway (open), the breach
            # position is already an archway threshold — skip, find a different candidate.
            above = cells.get((tx, ty, z_floor + 1))
            if above and above.system_building_element == StructureElement.ARCHWAY:
                continue
            result.add((ex, ey))
    return list(result)


def _sort_by_face(
    candidates: list[tuple[int, int]],
    corridor:   _RoomInstance,
) -> list[tuple[int, int]]:
    """Sort exterior candidates by proximity to the face end (far from origin)."""
    cx = corridor.origin_x + corridor.width  // 2
    cy = corridor.origin_y + corridor.depth  // 2
    # Face end is the centroid of the far half
    if corridor.depth >= corridor.width:
        face_y = corridor.origin_y + corridor.depth - 1
        return sorted(candidates, key=lambda p: -abs(p[1] - face_y))
    else:
        face_x = corridor.origin_x + corridor.width - 1
        return sorted(candidates, key=lambda p: -abs(p[0] - face_x))


def _min_wall_distance(A: _RoomInstance, B: _RoomInstance) -> int:
    a_fp = A.get_footprint()
    b_fp = B.get_footprint()
    best = 10**9
    for ax, ay in a_fp:
        for bx, by in b_fp:
            d = abs(ax - bx) + abs(ay - by)
            if d < best:
                best = d
    return best


# ---------------------------------------------------------------------------
# Width verification

def _verify_width(
    path:       list[tuple[int, int]],
    interior_w: int,
    all_fp:     set[tuple[int, int]],
) -> int:
    """Return interior_w if full expansion fits, else 1."""
    if interior_w <= 1:
        return 1
    half = interior_w // 2
    for i, (cx, cy) in enumerate(path):
        # Determine perpendicular direction at this cell
        if i == 0:
            dx, dy = path[1][0] - cx, path[1][1] - cy
        else:
            dx, dy = cx - path[i - 1][0], cy - path[i - 1][1]
        pdx, pdy = -dy, dx  # rotate 90°
        for offset in range(1, half + 1):
            for sign in (1, -1):
                ex, ey = cx + pdx * offset * sign, cy + pdy * offset * sign
                if (ex, ey) in all_fp:
                    return 1
    return interior_w


# ---------------------------------------------------------------------------
# Tunnel construction

def _build_tunnel(
    path:            list[tuple[int, int]],
    cells:           dict,
    world_uid:       str,
    building_uid:    str,
    wall_mat:        str,
    z_floor:         int,
    z_height:        int,
    A:               _RoomInstance,
    B:               _RoomInstance,
    non_corridor_fp: set[tuple[int, int]],
    width:           int,
    passage_height:  int,
) -> None:
    a_fp = A.get_footprint()
    b_fp = B.get_footprint()

    # Breach cells: footprint cells of A/B adjacent to path endpoints
    breach_a = _find_adjacent_fp_cell(path[0],  a_fp)
    breach_b = _find_adjacent_fp_cell(path[-1], b_fp)

    # All XY cells occupied by the tunnel (for side-wall exclusion)
    path_set: set[tuple[int, int]] = set(path)
    if breach_a:
        path_set.add(breach_a)
    if breach_b:
        path_set.add(breach_b)

    # Compute all path cells including perpendicular expansion
    all_path_cells = _expand_path(path, width)

    wu, bu = world_uid, building_uid
    passage_height = min(z_height - 1, passage_height)

    logger.info(
        "connect _build_tunnel | path[0]=%s path[-1]=%s breach_a=%s breach_b=%s",
        path[0], path[-1], breach_a, breach_b,
    )

    # Place floor + open for all path cells (skip cells belonging to non-corridor rooms)
    for cx, cy in all_path_cells:
        if (cx, cy) in non_corridor_fp:
            continue
        for z in range(z_floor, z_floor + z_height):
            key = (cx, cy, z)
            if key in cells:
                continue
            if z == z_floor:
                cells[key] = _floor_cell(cx, cy, z, wu, bu, wall_mat)
            else:
                cells[key] = _open_cell(cx, cy, z, wu, bu, wall_mat)

    # Side walls: all 8 neighbors not on path, not in non-corridor room footprint
    all_path_xy = {(cx, cy) for cx, cy in all_path_cells}
    for cx, cy in list(all_path_xy):
        for ddx in (-1, 0, 1):
            for ddy in (-1, 0, 1):
                if ddx == 0 and ddy == 0:
                    continue
                nx, ny = cx + ddx, cy + ddy
                if (nx, ny) in all_path_xy:
                    continue
                if (nx, ny) in non_corridor_fp:
                    continue
                for z in range(z_floor, z_floor + z_height):
                    key = (nx, ny, z)
                    if key not in cells:
                        cells[key] = _wall_cell(nx, ny, z, wu, bu, wall_mat)

    # Wall breach at A side
    if breach_a:
        facing_a = _VEC_TO_FACING.get(
            (path[0][0] - breach_a[0], path[0][1] - breach_a[1]), Facing.NORTH,
        )
        WallBreachPlacer(cells, wu, bu).place_for_corridor(
            breach_a[0], breach_a[1],
            z_floor, z_floor + z_height,
            wall_mat, facing_a, passage_height,
            f"connect:{A.room_id}→{B.room_id}",
        )

    # Wall breach at B side
    if breach_b:
        facing_b = _VEC_TO_FACING.get(
            (path[-1][0] - breach_b[0], path[-1][1] - breach_b[1]), Facing.NORTH,
        )
        WallBreachPlacer(cells, wu, bu).place_for_corridor(
            breach_b[0], breach_b[1],
            z_floor, z_floor + z_height,
            wall_mat, facing_b, passage_height,
            f"connect:{B.room_id}→{A.room_id}",
        )


def _find_adjacent_fp_cell(
    pt: tuple[int, int],
    fp: set[tuple[int, int]],
) -> tuple[int, int] | None:
    for dx, dy in _DIRS:
        nb = (pt[0] + dx, pt[1] + dy)
        if nb in fp:
            return nb
    return None


def _expand_path(
    path:  list[tuple[int, int]],
    width: int,
) -> list[tuple[int, int]]:
    if width <= 1:
        return list(path)

    half = width // 2
    result: set[tuple[int, int]] = set(path)
    for i, (cx, cy) in enumerate(path):
        if i == 0:
            dx, dy = path[1][0] - cx, path[1][1] - cy
        else:
            dx, dy = cx - path[i - 1][0], cy - path[i - 1][1]
        pdx, pdy = -dy, dx
        for offset in range(1, half + 1):
            for sign in (1, -1):
                result.add((cx + pdx * offset * sign, cy + pdy * offset * sign))
    return list(result)
