"""Entry-wall constraints in the author frame, before cells are built."""
import logging

from app.dataModel.spatial.facing import Facing, CARDINAL_WALL_OUTWARD_DELTA
from app.dataModel.structure.room.entryPoint import EntryPoint
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance

logger = logging.getLogger(__name__)


def entries(room: _RoomInstance) -> tuple[tuple[str, EntryPoint | None], ...]:
    return (("entry_point", room.entry_point), ("back_entry_point", room.back_entry_point))


def has_entry_wall(room: _RoomInstance, wall: Facing, width: int,
                   union: set[tuple[int, int]]) -> bool:
    """Require exterior space and an interior floor behind the opening."""
    fp = room.get_footprint()
    dx, dy = CARDINAL_WALL_OUTWARD_DELTA[wall]
    interior = {p for p in fp if all((p[0] + vx, p[1] + vy) in fp
                                   for vx, vy in CARDINAL_WALL_OUTWARD_DELTA.values())}
    return sum((x + dx, y + dy) not in union and (x - dx, y - dy) in interior
               for x, y in fp) >= width


def entries_exterior(room: _RoomInstance, union: set[tuple[int, int]]) -> bool:
    return all(has_entry_wall(room, ep.wall, ep.width, union)
               for _, ep in entries(room) if ep is not None)


def blocks_entries(room: _RoomInstance, placed: list[_RoomInstance]) -> bool:
    hosts = [p for p in placed if p is not room and (p.entry_point or p.back_entry_point)]
    if not hosts:
        return False
    union = set().union(*(p.get_footprint() for p in placed if p is not room))
    extended = union | room.get_footprint()
    return any(entries_exterior(host, union) and not entries_exterior(host, extended)
               for host in hosts)


def resolve_entry_walls(room: _RoomInstance, union: set[tuple[int, int]]) -> None:
    """Fallback changes only runtime entries; the authored POJO stays frozen."""
    replacements = []
    for field, ep in entries(room):
        if ep is None or has_entry_wall(room, ep.wall, ep.width, union):
            continue
        wall = next((side for side in CARDINAL_WALL_OUTWARD_DELTA
                     if has_entry_wall(room, side, ep.width, union)), None)
        if wall is None:
            raise GenerationError(f"Room {room.room_id!r}: no exterior perimeter for {field}")
        replacements.append((field, ep, wall))
    for field, ep, wall in replacements:
        logger.warning("Room %r: %s.wall=%s unreachable — placed on another perimeter (%s)",
                       room.room_id, field, ep.wall.value, wall.value)
        setattr(room, field, ep.model_copy(update={"wall": wall}))
