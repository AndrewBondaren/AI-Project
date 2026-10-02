"""Place embedded upper stops directly above their source, or skip with ERROR."""
import logging

from app.application.worldData.generators.structure.cellBuilder import _interior
from app.application.worldData.generators.structure.layoutEngine import _interior_overlaps
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.dataModel.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.spatial.facing import Facing, CARDINAL_WALL_OUTWARD_DELTA, opposite

logger = logging.getLogger(__name__)


def embedded_wall(shaft: _RoomInstance, side: Facing) -> list[tuple[int, int]]:
    x, y = shaft.origin_x, shaft.origin_y
    match side:
        case Facing.NORTH:
            return [(wx, y + shaft.depth - 1) for wx in range(x + 1, x + shaft.width - 1)]
        case Facing.SOUTH:
            return [(wx, y) for wx in range(x + 1, x + shaft.width - 1)]
        case Facing.EAST:
            return [(x + shaft.width - 1, wy) for wy in range(y + 1, y + shaft.depth - 1)]
        case Facing.WEST:
            return [(x, wy) for wy in range(y + 1, y + shaft.depth - 1)]
        case _:
            raise ValueError(f"Embedded exit wall must be cardinal: {side}")


def _resolve_stop(candidates: list[_RoomInstance], role: str) -> tuple[_RoomInstance | None, str | None]:
    match candidates:
        case []:
            return None, f"{role} room missing"
        case [room] if role == "source" and not room.placed:
            return room, "source room missing from layout: not placed"
        case [room]:
            return room, None
        case _:
            return None, f"{role} room ambiguous: {len(candidates)} instances (count must be 1)"


def _align_host(source: _RoomInstance, target: _RoomInstance, shaft: _RoomInstance,
                rooms: list[_RoomInstance], bounds: tuple[int, int, int, int] | None) -> str | None:
    match target, shaft:
        case _RoomInstance(layout_excluded=True), _:
            return "target already excluded by another staircase contract"
        case _, _RoomInstance(origin_x=None):
            return "inherited shaft is not placed"
        case _RoomInstance(layout_locked=True), _ if (target.origin_x, target.origin_y) != (source.origin_x, source.origin_y):
            return "another staircase requires a different target XY"

    target.origin_x, target.origin_y = source.origin_x, source.origin_y
    fp = target.get_footprint()
    if bounds is not None and any(not (bounds[0] <= x <= bounds[2] and
                                       bounds[1] <= y <= bounds[3]) for x, y in fp):
        return "target exceeds parent floor bounds; shrinking or relocating violates contract"
    if not shaft.get_footprint() <= fp:
        return "target footprint does not contain inherited shaft"
    conflicts = [r.uid_key for r in rooms if r is not target and r is not shaft
                 and r.placed and r.z_offset == shaft.z_offset
                 and not (r.is_shaft and r.embedded_host_key == target.uid_key)
                 and _interior_overlaps(target, r)]
    if conflicts:
        return f"target overlaps placed rooms/shafts {conflicts}"

    interior = _interior(fp)
    preferred = opposite(Facing(shaft.facing))
    sides = dict.fromkeys([preferred, *CARDINAL_WALL_OUTWARD_DELTA])
    side = next((side for side in sides
                 if all((x + CARDINAL_WALL_OUTWARD_DELTA[side][0],
                         y + CARDINAL_WALL_OUTWARD_DELTA[side][1]) in interior
                        for x, y in embedded_wall(shaft, side))), None)
    if side is None:
        return "no interior floor along any shaft exit wall"
    target.layout_locked = True
    shaft.layout_locked = True
    shaft.embedded_host_key = target.uid_key
    shaft.embedded_entry = side
    return None


def _exclude_targets(targets: list[_RoomInstance], rooms: list[_RoomInstance],
                     abandoned: list[_RoomInstance], z_offset: int) -> None:
    host_keys = {room.uid_key for room in targets}
    attached = [r for r in rooms if r.is_shaft and r.z_offset == z_offset
                and r.embedded_host_key in host_keys]
    for room in [*targets, *attached, *abandoned]:
        room.origin_x = room.origin_y = None
        room.layout_excluded = True


def prepare_embedded_upper(z_offset: int, rooms: list[_RoomInstance],
                           staircases: list[StaircaseSpec], shafts_by_id: dict[str, list[_RoomInstance]],
                           bounds: tuple[int, int, int, int] | None,
                           building_uid: str) -> None:
    for sc in staircases:
        shafts = shafts_by_id.get(sc.staircase_id, [])
        if not sc.in_a_room or not shafts:
            continue
        # Preserve the previously defined adjacent fallback for failed lower embedding.
        if shafts[0].placed and shafts[0].embedded_entry is None:
            continue
        for i in range(1, min(len(sc.stops), len(shafts))):
            shaft = shafts[i]
            if shaft.z_offset != z_offset:
                continue
            sources = [r for r in rooms if not r.is_shaft and r.room_id == sc.stops[i - 1]]
            targets = [r for r in rooms if not r.is_shaft and r.room_id == sc.stops[i]]
            source, source_error = _resolve_stop(sources, "source")
            target, target_error = _resolve_stop(targets, "target")
            reason = source_error or target_error
            if reason is None:
                reason = _align_host(source, target, shaft, rooms, bounds)
            if reason is not None:
                logger.error(
                    "embedded upper contract | building=%s staircase=%r from_room=%r to_room=%r "
                    "z=%d source_z=%s source_xy=%s target_size=%s shaft_xy=%s shaft_size=%s bounds=%s "
                    "target not created: %s",
                    building_uid, sc.staircase_id, sc.stops[i - 1], sc.stops[i], z_offset,
                    source.z_offset if source else None,
                    (source.origin_x, source.origin_y) if source else None,
                    (target.width, target.depth) if target else None,
                    (shaft.origin_x, shaft.origin_y), (shaft.width, shaft.depth), bounds, reason,
                )
                _exclude_targets(targets, rooms, shafts[i:], z_offset)
