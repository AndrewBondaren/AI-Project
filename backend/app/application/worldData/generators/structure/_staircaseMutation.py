"""
Stairwell mutation: expands a room's footprint at one end to fit a staircase.

Triggered when:
  - Connection is a staircase
  - Resolved type (before fallback) is NOT ladder or trapdoor
    (i.e. economic tier implies a real staircase)
  - The staircase doesn't fit in to_room as-is

Mutation: adds extra_cells to to_room forming a landing alcove at one end.
The alcove has the same room UID — no door, no separate room.
extra_cells are included in get_footprint(), so all downstream passes
(cell builder, passage builder) use the extended shape automatically.
"""
import logging
import math

from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel
from app.db.models.world import World

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers

def _block_size(stair_type: str, z_height: int) -> tuple[int, int]:
    """(width, depth) of the staircase block footprint."""
    if stair_type in ("ladder", "trapdoor"):
        return (1, 1)
    if stair_type in ("standard", "spiral_standard"):
        return (2, 2)
    if stair_type == "spiral_small":
        return (1, 2)
    if stair_type == "straight":
        length = max(2, math.ceil(z_height * 1.3))
        return (2, length)
    return (1, 1)


# ---------------------------------------------------------------------------
# Core mutation

def _mutate_room(
    room: _RoomInstance,
    stair_type: str,
    z_height: int,
    all_rooms: list[_RoomInstance],
) -> bool:
    """
    Adds extra_cells to room to accommodate stair_type.
    Tries all 4 candidate positions (west/east × south/north for horizontal room).
    Returns True if a non-overlapping candidate was found.
    """
    block_w, block_h = _block_size(stair_type, z_height)

    other_fp: set[tuple[int, int]] = set()
    for r in all_rooms:
        if r.placed and r is not room:
            other_fp |= r.get_footprint()

    fp  = room.get_footprint()
    xs  = sorted({x for (x, _) in fp})
    ys  = sorted({y for (_, y) in fp})
    x_min, x_max = xs[0], xs[-1]
    y_min, y_max = ys[0], ys[-1]
    x_span = x_max - x_min + 1
    y_span = y_max - y_min + 1

    candidates: list[tuple[set[tuple[int, int]], str]] = []

    if x_span >= y_span:
        # Horizontal room — extend along y (depth), at west or east end of x
        extra_rows = (block_h + 2) - y_span   # how many y rows to add
        if extra_rows <= 0:
            return False
        ext_xw = block_w + 2   # x-width of the alcove (block + 1-cell perimeter each side)

        for x_lo, end_label in [
            (x_min,                    "west"),
            (max(x_min, x_max - ext_xw + 1), "east"),
        ]:
            x_hi = min(x_lo + ext_xw - 1, x_max)
            for dy, dir_label in [(-1, "south"), (1, "north")]:
                new_cells: set[tuple[int, int]] = set()
                for row in range(extra_rows):
                    y_new = (y_min - 1 - row) if dy == -1 else (y_max + 1 + row)
                    for x in range(x_lo, x_hi + 1):
                        new_cells.add((x, y_new))
                candidates.append((new_cells, f"{end_label}-{dir_label}"))
    else:
        # Vertical room — extend along x (width), at south or north end of y
        extra_cols = (block_w + 2) - x_span
        if extra_cols <= 0:
            return False
        ext_yh = block_h + 2

        for y_lo, end_label in [
            (y_min,                    "south"),
            (max(y_min, y_max - ext_yh + 1), "north"),
        ]:
            y_hi = min(y_lo + ext_yh - 1, y_max)
            for dx, dir_label in [(-1, "west"), (1, "east")]:
                new_cells = set()
                for col in range(extra_cols):
                    x_new = (x_min - 1 - col) if dx == -1 else (x_max + 1 + col)
                    for y in range(y_lo, y_hi + 1):
                        new_cells.add((x_new, y))
                candidates.append((new_cells, f"{end_label}-{dir_label}"))

    for new_cells, label in candidates:
        if not (new_cells & other_fp):
            room.extra_cells |= new_cells
            logger.info(
                "stairwell_mutation | room=%r: added %d cells (%s) for %s",
                room.room_id, len(new_cells), label, stair_type,
            )
            return True

    return False


# ---------------------------------------------------------------------------
# Public entry point

def apply_stairwell_mutations(
    connections: list[dict],
    all_rooms: list[_RoomInstance],
    room_z_offsets: dict[str, int],
    levels: dict[int, LocationLevel],
    world: World,
    template: dict,
    building_tier: str | None = None,
) -> None:
    """
    Scan staircase connections and mutate to_room where needed.
    Modifies _RoomInstance.extra_cells in-place.
    Called after layout, before cell building.
    """
    from app.application.worldData.generators.structure._passageBuilder import (
        _resolve_staircase_type,
        _stair_fits,
    )

    logger.info("=== PHASE: stairwell_mutation ===")

    placed_by_id: dict[str, list[_RoomInstance]] = {}
    for r in all_rooms:
        if r.placed:
            placed_by_id.setdefault(r.room_id, []).append(r)

    staircase_conns = [c for c in connections if c.get("passage_type") == "staircase"]
    logger.info("stairwell_mutation | checking %d staircase connection(s)", len(staircase_conns))

    for conn in staircase_conns:
        fr_list = placed_by_id.get(conn["from_room"], [])
        to_list = placed_by_id.get(conn["to_room"],   [])
        if not fr_list or not to_list:
            logger.debug(
                "stairwell_mutation | %s->%s: skipped (room not placed)",
                conn["from_room"], conn["to_room"],
            )
            continue

        fr_room = fr_list[0]
        to_room = to_list[0]

        fr_offset = room_z_offsets.get(conn["from_room"])
        to_offset = room_z_offsets.get(conn["to_room"])
        if fr_offset is None or to_offset is None:
            continue

        z_height = abs(levels[to_offset].z - levels[fr_offset].z)
        desired  = _resolve_staircase_type(conn, fr_room, to_room, template, world, z_height, building_tier)

        logger.info(
            "stairwell_mutation | %s->%s: desired=%s to_room=%r size=%dx%d z_height=%d",
            conn["from_room"], conn["to_room"], desired,
            to_room.room_id, to_room.width, to_room.depth, z_height,
        )

        if desired in ("ladder", "trapdoor"):
            logger.info(
                "stairwell_mutation | %s->%s: skipped -- %s needs no structural fit",
                conn["from_room"], conn["to_room"], desired,
            )
            continue

        already_fits = _stair_fits(desired, to_room, z_height, include_extra=False)
        if already_fits:
            logger.info(
                "stairwell_mutation | %s->%s: no mutation needed -- %s already fits",
                conn["from_room"], conn["to_room"], desired,
            )
            continue

        logger.info(
            "stairwell_mutation | %s->%s: %s does NOT fit in %dx%d interior -- mutating",
            conn["from_room"], conn["to_room"], desired,
            max(0, to_room.width - 2), max(0, to_room.depth - 2),
        )

        ok = _mutate_room(to_room, desired, z_height, all_rooms)
        if ok:
            logger.info(
                "stairwell_mutation | %s->%s: to_room=%r mutated -- extra_cells=%d total_footprint=%d",
                conn["from_room"], conn["to_room"], to_room.room_id,
                len(to_room.extra_cells), len(to_room.get_footprint()),
            )
        else:
            logger.warning(
                "stairwell_mutation | %s->%s: to_room=%r BLOCKED on all sides -- "
                "staircase will fallback to ladder",
                conn["from_room"], conn["to_room"], to_room.room_id,
            )

    logger.info("=== END PHASE: stairwell_mutation ===")
