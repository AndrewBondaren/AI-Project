"""
Layout engine: sets origin_x/origin_y on each _RoomInstance.

Coordinate system: x increases east, y increases north.

Adjacent rooms share ONE perimeter column/row:
  place B east of A  →  B.x0 = A.x0 + A.width - 1   (share east column)
  place B north of A →  B.y0 = A.y0 + A.depth - 1   (share north row)
  place B west of A  →  B.x0 = A.x0 - B.width + 1
  place B south of A →  B.y0 = A.y0 - B.depth + 1

Overlap rule: interior bounding boxes must not intersect.
Interior = full bbox shrunk by 1 on each side (excludes perimeter).
"""
import logging
from collections import deque

from app.application.worldData.generators.structure._errors import GenerationError
from app.application.worldData.generators.structure._roomInstance import _RoomInstance

logger = logging.getLogger(__name__)

_DIRECTIONS = ("east", "north", "west", "south")


# ---------------------------------------------------------------------------
# Helpers

def _by_id(rooms: list[_RoomInstance], room_id: str) -> _RoomInstance | None:
    for r in rooms:
        if r.room_id == room_id:
            return r
    return None


def _interior_overlaps(a: _RoomInstance, b: _RoomInstance) -> bool:
    """True if interiors (bbox shrunk by 1) of two placed rooms intersect."""
    ax0 = a.origin_x + 1;  ax1 = a.origin_x + a.width  - 2
    ay0 = a.origin_y + 1;  ay1 = a.origin_y + a.depth  - 2
    bx0 = b.origin_x + 1;  bx1 = b.origin_x + b.width  - 2
    by0 = b.origin_y + 1;  by1 = b.origin_y + b.depth  - 2
    return ax0 <= bx1 and bx0 <= ax1 and ay0 <= by1 and by0 <= ay1


def _has_conflict(room: _RoomInstance, placed: list[_RoomInstance]) -> bool:
    return any(_interior_overlaps(room, p) for p in placed if p is not room)


def _origin_adjacent(room: _RoomInstance, anchor: _RoomInstance, direction: str) -> tuple[int, int]:
    """Compute (x0, y0) to place room adjacent to anchor in given direction."""
    ax, ay = anchor.origin_x, anchor.origin_y
    aw, ad = anchor.width, anchor.depth
    if direction == "east":
        return ax + aw - 1, ay
    if direction == "north":
        return ax, ay + ad - 1
    if direction == "west":
        return ax - room.width + 1, ay
    # south
    return ax, ay - room.depth + 1


def _try_adjacent(room: _RoomInstance, anchor: _RoomInstance, direction: str,
                  placed: list[_RoomInstance]) -> bool:
    x0, y0 = _origin_adjacent(room, anchor, direction)
    room.origin_x, room.origin_y = x0, y0
    if _has_conflict(room, placed):
        room.origin_x = room.origin_y = None
        return False
    return True


def _place_next_to_any(room: _RoomInstance, placed: list[_RoomInstance]) -> bool:
    """Try all directions against all placed rooms. First success wins."""
    for anchor in placed:
        for direction in _DIRECTIONS:
            if _try_adjacent(room, anchor, direction, placed):
                return True
    return False


def _spiral_search(room: _RoomInstance, placed: list[_RoomInstance],
                   origin: tuple[int, int]) -> bool:
    """Expand outward from origin to find first non-conflicting position."""
    ox, oy = origin
    step_x = max(r.width  for r in placed) if placed else room.width
    step_y = max(r.depth for r in placed) if placed else room.depth

    for radius in range(1, 30):
        candidates = []
        for dx in range(-radius, radius + 1):
            for dy in (-radius, radius):
                candidates.append((ox + dx * step_x, oy + dy * step_y))
        for dy in range(-radius + 1, radius):
            for dx in (-radius, radius):
                candidates.append((ox + dx * step_x, oy + dy * step_y))
        for x0, y0 in candidates:
            room.origin_x, room.origin_y = x0, y0
            if not _has_conflict(room, placed):
                return True
    room.origin_x = room.origin_y = None
    return False


# ---------------------------------------------------------------------------
# Graph helpers

def _build_graph(rooms: list[_RoomInstance], connections: list[dict]) -> dict[str, set[str]]:
    """Intra-level adjacency graph (doorway/archway only, no staircases)."""
    ids = {r.room_id for r in rooms}
    graph: dict[str, set[str]] = {r.room_id: set() for r in rooms}
    for conn in connections:
        fr, tr = conn["from_room"], conn["to_room"]
        if conn.get("passage_type") != "staircase" and fr in ids and tr in ids:
            graph[fr].add(tr)
            graph[tr].add(fr)
    return graph


def _find_start(rooms: list[_RoomInstance], connections: list[dict],
                graph: dict[str, set[str]]) -> _RoomInstance:
    for r in rooms:
        if r.entry_point:
            return r
    ids = {r.room_id for r in rooms}
    for conn in connections:
        if conn.get("passage_type") == "staircase":
            for candidate_id in (conn.get("to_room"), conn.get("from_room")):
                if candidate_id in ids:
                    r = _by_id(rooms, candidate_id)
                    if r:
                        return r
    return max(rooms, key=lambda r: len(graph.get(r.room_id, set())))


# ---------------------------------------------------------------------------
# Mode A — BFS

def _layout_mode_a(rooms: list[_RoomInstance], connections: list[dict],
                   bx: int, by: int) -> None:
    if not rooms:
        return

    graph = _build_graph(rooms, connections)
    start = _find_start(rooms, connections, graph)
    logger.info("layout mode_a | start_room=%s total=%d", start.room_id, len(rooms))

    placed: list[_RoomInstance] = []
    visited: set[str] = set()
    queue: deque[_RoomInstance] = deque([start])

    start.origin_x, start.origin_y = bx, by
    placed.append(start)
    visited.add(start.room_id)

    while queue:
        current = queue.popleft()
        for nid in graph.get(current.room_id, set()):
            if nid in visited:
                continue
            visited.add(nid)
            nbr = _by_id(rooms, nid)
            if nbr is None or nbr.placed:
                continue
            queue.append(nbr)

            # Try to place adjacent to current first, then any placed room
            placed_ok = _try_adjacent(nbr, current, _DIRECTIONS[0], placed)
            if not placed_ok:
                placed_ok = _place_next_to_any(nbr, placed)

            if placed_ok:
                placed.append(nbr)
            elif not nbr.required:
                logger.warning("layout mode_a | room=%r z=%d skipped — no space", nbr.room_id, nbr.z_offset)
            else:
                raise GenerationError(f"Room {nbr.room_id!r}: no space on level")

    # Isolated vertices (no connections)
    for room in rooms:
        if room.placed:
            continue
        ref = placed[-1] if placed else None
        ox = ref.origin_x if ref else bx
        oy = ref.origin_y if ref else by
        if _spiral_search(room, placed, (ox, oy)):
            placed.append(room)
        elif room.required:
            raise GenerationError(f"Room {room.room_id!r}: isolated, no space")
        else:
            logger.warning("layout mode_a | room=%r z=%d skipped — isolated, no space", room.room_id, room.z_offset)


# ---------------------------------------------------------------------------
# Mode B — corridor attach_to

def _layout_mode_b(rooms: list[_RoomInstance], all_placed: list[_RoomInstance]) -> None:
    attach_rooms = [r for r in rooms if r.attach_to is not None and not r.placed]
    if not attach_rooms:
        return
    logger.info("layout mode_b | attach_rooms=%d", len(attach_rooms))

    by_host: dict[str, list[_RoomInstance]] = {}
    for r in attach_rooms:
        by_host.setdefault(r.attach_to, []).append(r)

    for host_id, group in by_host.items():
        host = _by_id(all_placed, host_id)
        if host is None or not host.placed:
            logger.warning("layout mode_b | host=%r not placed — skipping %d attached room(s)", host_id, len(attached))
            continue

        attach_wall = group[0].attach_wall or "both"

        north_side: list[_RoomInstance] = []
        south_side: list[_RoomInstance] = []
        for i, room in enumerate(group):
            if attach_wall == "north":
                north_side.append(room)
            elif attach_wall == "south":
                south_side.append(room)
            else:  # "both" or "any"
                (north_side if i % 2 == 0 else south_side).append(room)

        # North side: rooms placed above host, sharing host's north perimeter
        cursor_x = host.origin_x + 1
        for room in north_side:
            room.origin_x = cursor_x
            room.origin_y = host.origin_y + host.depth - 1  # share north wall
            if not _has_conflict(room, all_placed):
                all_placed.append(room)
                cursor_x += room.width - 1
            elif room.required:
                raise GenerationError(f"Room {room.room_id!r}: no corridor slot (north)")
            else:
                logger.warning("layout mode_b | room=%r z=%d skipped — corridor north wall full", room.room_id, room.z_offset)
                room.origin_x = room.origin_y = None

        # South side: rooms placed below host, sharing host's south perimeter
        cursor_x = host.origin_x + 1
        for room in south_side:
            room.origin_x = cursor_x
            room.origin_y = host.origin_y - room.depth + 1  # share south wall
            if not _has_conflict(room, all_placed):
                all_placed.append(room)
                cursor_x += room.width - 1
            elif room.required:
                raise GenerationError(f"Room {room.room_id!r}: no corridor slot (south)")
            else:
                logger.warning("layout mode_b | room=%r z=%d skipped — corridor south wall full", room.room_id, room.z_offset)
                room.origin_x = room.origin_y = None


# ---------------------------------------------------------------------------
# Public entry point

def layout_level(
    rooms: list[_RoomInstance],
    connections: list[dict],
    building_x: int,
    building_y: int,
) -> None:
    """
    Places all rooms on a level in-place.
    Mode A (BFS) runs first; Mode B (attach_to) runs after.
    """
    mode_a_rooms = [r for r in rooms if r.attach_to is None]
    _layout_mode_a(mode_a_rooms, connections, building_x, building_y)

    all_placed = [r for r in rooms if r.placed]
    _layout_mode_b(rooms, all_placed)
