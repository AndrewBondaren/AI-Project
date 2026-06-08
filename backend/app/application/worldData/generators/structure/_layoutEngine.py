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

def _place_rooms_on_side(
    side: str,
    rooms: list[_RoomInstance],
    host: _RoomInstance,
    all_placed: list[_RoomInstance],
    bounds: tuple[int, int, int, int] | None,
) -> None:
    """
    Place rooms along one side of host.

    north/south: cursor moves along x, rooms extend perpendicularly in y.
    east/west:   cursor moves along y, rooms extend perpendicularly in x.
    """
    horizontal = side in ("north", "south")
    cursor = host.origin_x if horizontal else host.origin_y

    for room in rooms:
        # Set initial origin
        if side == "north":
            room.origin_x = cursor
            room.origin_y = host.origin_y + host.depth - 1
        elif side == "south":
            room.origin_x = cursor
            room.origin_y = None  # resolved after depth clamp
        elif side == "east":
            room.origin_x = host.origin_x + host.width - 1
            room.origin_y = cursor
        else:  # west
            room.origin_x = None  # resolved after width clamp
            room.origin_y = cursor

        if bounds is not None:
            x_min, y_min, x_max, y_max = bounds

            if side == "north":
                # Extent: y grows north — clamp depth by y_max
                avail_d = y_max - room.origin_y + 1
                clamped_d = max(1, min(room.depth, avail_d))
                if clamped_d != room.depth:
                    logger.info("layout mode_b | room=%r north depth %d->%d", room.room_id, room.depth, clamped_d)
                    room.depth = clamped_d
                # Cursor: x grows east — clamp width by x_max
                if cursor + room.width - 1 > x_max:
                    clamped_w = x_max - cursor + 1
                    if clamped_w < 3:
                        logger.warning("layout mode_b | room=%r z=%d skipped — no x-space (north, x_max=%d)", room.room_id, room.z_offset, x_max)
                        room.origin_x = room.origin_y = None
                        continue
                    logger.info("layout mode_b | room=%r north width %d->%d", room.room_id, room.width, clamped_w)
                    room.width = clamped_w

            elif side == "south":
                # Extent: y grows south — available = host.origin_y - y_min + 1
                avail_d = host.origin_y - y_min + 1
                clamped_d = max(1, min(room.depth, avail_d))
                if clamped_d != room.depth:
                    logger.info("layout mode_b | room=%r south depth %d->%d", room.room_id, room.depth, clamped_d)
                    room.depth = clamped_d
                # Cursor: x grows east — clamp width by x_max
                if cursor + room.width - 1 > x_max:
                    clamped_w = x_max - cursor + 1
                    if clamped_w < 3:
                        logger.warning("layout mode_b | room=%r z=%d skipped — no x-space (south, x_max=%d)", room.room_id, room.z_offset, x_max)
                        room.origin_x = room.origin_y = None
                        continue
                    logger.info("layout mode_b | room=%r south width %d->%d", room.room_id, room.width, clamped_w)
                    room.width = clamped_w

            elif side == "east":
                # Extent: x grows east — clamp width by x_max
                avail_w = x_max - room.origin_x + 1
                clamped_w = max(1, min(room.width, avail_w))
                if clamped_w < 3:
                    logger.warning("layout mode_b | room=%r z=%d skipped — no x-space (east, x_max=%d)", room.room_id, room.z_offset, x_max)
                    room.origin_x = room.origin_y = None
                    continue
                if clamped_w != room.width:
                    logger.info("layout mode_b | room=%r east width %d->%d", room.room_id, room.width, clamped_w)
                    room.width = clamped_w
                # Cursor: y grows north — clamp depth by y_max
                if cursor + room.depth - 1 > y_max:
                    clamped_d = y_max - cursor + 1
                    if clamped_d < 3:
                        logger.warning("layout mode_b | room=%r z=%d skipped — no y-space (east, y_max=%d)", room.room_id, room.z_offset, y_max)
                        room.origin_x = room.origin_y = None
                        continue
                    logger.info("layout mode_b | room=%r east depth %d->%d", room.room_id, room.depth, clamped_d)
                    room.depth = clamped_d

            else:  # west
                # Extent: x grows west — available = host.origin_x - x_min + 1
                avail_w = host.origin_x - x_min + 1
                clamped_w = max(1, min(room.width, avail_w))
                if clamped_w < 3:
                    logger.warning("layout mode_b | room=%r z=%d skipped — no x-space (west, x_min=%d)", room.room_id, room.z_offset, x_min)
                    room.origin_x = room.origin_y = None
                    continue
                if clamped_w != room.width:
                    logger.info("layout mode_b | room=%r west width %d->%d", room.room_id, room.width, clamped_w)
                    room.width = clamped_w
                # Cursor: y grows north — clamp depth by y_max
                if cursor + room.depth - 1 > y_max:
                    clamped_d = y_max - cursor + 1
                    if clamped_d < 3:
                        logger.warning("layout mode_b | room=%r z=%d skipped — no y-space (west, y_max=%d)", room.room_id, room.z_offset, y_max)
                        room.origin_x = room.origin_y = None
                        continue
                    logger.info("layout mode_b | room=%r west depth %d->%d", room.room_id, room.depth, clamped_d)
                    room.depth = clamped_d

        # Resolve deferred origin components
        if side == "south":
            room.origin_y = host.origin_y - room.depth + 1
        elif side == "west":
            room.origin_x = host.origin_x - room.width + 1

        # 2×2 interior check — both dims ≤ 2 is not a usable room
        if (room.width - 2) <= 2 and (room.depth - 2) <= 2:
            logger.warning(
                "layout mode_b | room=%r z=%d skipped — interior %dx%d (both dims ≤ 2)",
                room.room_id, room.z_offset, room.width - 2, room.depth - 2,
            )
            room.origin_x = room.origin_y = None
            continue

        if not _has_conflict(room, all_placed):
            all_placed.append(room)
            cursor += (room.width - 1) if horizontal else (room.depth - 1)
        elif room.required:
            raise GenerationError(f"Room {room.room_id!r}: no corridor slot ({side})")
        else:
            logger.warning("layout mode_b | room=%r z=%d skipped — %s wall full", room.room_id, room.z_offset, side)
            room.origin_x = room.origin_y = None


def _layout_mode_b(
    rooms: list[_RoomInstance],
    all_placed: list[_RoomInstance],
    bounds: tuple[int, int, int, int] | None = None,
) -> None:
    """
    bounds = (x_min, y_min, x_max, y_max) of the level below.

    attach_wall values: "north", "south", "east", "west" — explicit side.
    "both" / "any" — auto-detect from host orientation:
      horizontal host (width >= depth) → north + south
      vertical host   (depth > width)  → east  + west
    """
    attach_rooms = [r for r in rooms if r.attach_to is not None and not r.placed]
    if not attach_rooms:
        return
    logger.info("layout mode_b | attach_rooms=%d  bounds=%s", len(attach_rooms), bounds)

    by_host: dict[str, list[_RoomInstance]] = {}
    for r in attach_rooms:
        by_host.setdefault(r.attach_to, []).append(r)

    for host_id, group in by_host.items():
        host = _by_id(all_placed, host_id)
        if host is None or not host.placed:
            logger.warning("layout mode_b | host=%r not placed — skipping %d attached room(s)", host_id, len(group))
            continue

        attach_wall = group[0].attach_wall or "both"

        if attach_wall in ("north", "south", "east", "west"):
            _place_rooms_on_side(attach_wall, group, host, all_placed, bounds)
        else:  # "both" or "any" — auto-detect from host orientation
            horizontal = host.width >= host.depth
            side_a = "north" if horizontal else "east"
            side_b = "south" if horizontal else "west"
            side_a_rooms = [group[i] for i in range(0, len(group), 2)]
            side_b_rooms = [group[i] for i in range(1, len(group), 2)]
            _place_rooms_on_side(side_a, side_a_rooms, host, all_placed, bounds)
            _place_rooms_on_side(side_b, side_b_rooms, host, all_placed, bounds)


# ---------------------------------------------------------------------------
# Bounds clipping

def _clip_to_bounds(rooms: list[_RoomInstance], bounds: tuple[int, int, int, int]) -> None:
    """
    After mode A placement, clip any room dimension that extends beyond bounds.
    Mode B pre-clamps north/south depth using available space; this catches
    east/west overhangs from mode A (e.g. corridor extending past x_max).
    Must run BEFORE mode B so attached rooms use the corrected host dimensions.
    """
    x_min, y_min, x_max, y_max = bounds
    for room in rooms:
        if not room.placed:
            continue
        # East overhang
        east = room.origin_x + room.width - 1
        if east > x_max:
            if room.origin_x > x_max - 2:
                # No space for even a minimal room — unplace
                logger.warning(
                    "clip_to_bounds | room=%r unplaced — origin_x=%d leaves no space (x_max=%d)",
                    room.room_id, room.origin_x, x_max,
                )
                room.origin_x = room.origin_y = None
                continue
            new_w = x_max - room.origin_x + 1
            logger.info(
                "clip_to_bounds | room=%r width %d->%d (x_max=%d)",
                room.room_id, room.width, new_w, x_max,
            )
            room.width = new_w
        # West overhang
        if room.placed and room.origin_x < x_min:
            if room.origin_x + room.width - 1 < x_min + 2:
                logger.warning(
                    "clip_to_bounds | room=%r unplaced — east edge=%d leaves no space (x_min=%d)",
                    room.room_id, room.origin_x + room.width - 1, x_min,
                )
                room.origin_x = room.origin_y = None
                continue
            overshoot = x_min - room.origin_x
            new_w = room.width - overshoot
            logger.info(
                "clip_to_bounds | room=%r west overshoot=%d width %d->%d, origin_x %d->%d",
                room.room_id, overshoot, room.width, new_w, room.origin_x, x_min,
            )
            room.origin_x = x_min
            room.width = new_w
        # North overhang (mode B handles depth pre-clamp; this catches mode A rooms)
        if not room.placed:
            continue
        north = room.origin_y + room.depth - 1
        if north > y_max:
            if room.origin_y > y_max - 2:
                logger.warning(
                    "clip_to_bounds | room=%r unplaced — origin_y=%d leaves no space (y_max=%d)",
                    room.room_id, room.origin_y, y_max,
                )
                room.origin_x = room.origin_y = None
                continue
            new_d = y_max - room.origin_y + 1
            logger.info(
                "clip_to_bounds | room=%r depth %d->%d (y_max=%d)",
                room.room_id, room.depth, new_d, y_max,
            )
            room.depth = new_d
        # South overhang
        if room.placed and room.origin_y < y_min:
            if room.origin_y + room.depth - 1 < y_min + 2:
                logger.warning(
                    "clip_to_bounds | room=%r unplaced — north edge=%d leaves no space (y_min=%d)",
                    room.room_id, room.origin_y + room.depth - 1, y_min,
                )
                room.origin_x = room.origin_y = None
                continue
            overshoot = y_min - room.origin_y
            new_d = room.depth - overshoot
            logger.info(
                "clip_to_bounds | room=%r south overshoot=%d depth %d->%d, origin_y %d->%d",
                room.room_id, overshoot, room.depth, new_d, room.origin_y, y_min,
            )
            room.origin_y = y_min
            room.depth = new_d


# ---------------------------------------------------------------------------
# Public entry point

def layout_level(
    rooms: list[_RoomInstance],
    connections: list[dict],
    building_x: int,
    building_y: int,
    bounds: tuple[int, int, int, int] | None = None,
) -> None:
    """
    Places all rooms on a level in-place.
    Mode A (BFS) runs first; Mode B (attach_to) runs after.

    bounds = (x_min, y_min, x_max, y_max) of the parent level's footprint.
    Mode A rooms are clipped to bounds BEFORE mode B runs, so attached rooms
    are positioned relative to already-corrected host dimensions.
    """
    mode_a_rooms = [r for r in rooms if r.attach_to is None]
    _layout_mode_a(mode_a_rooms, connections, building_x, building_y)

    # Clip mode A rooms to parent bounds before attaching mode B rooms to them.
    if bounds is not None:
        _clip_to_bounds([r for r in mode_a_rooms if r.placed], bounds)

    all_placed = [r for r in rooms if r.placed]
    _layout_mode_b(rooms, all_placed, bounds=bounds)
