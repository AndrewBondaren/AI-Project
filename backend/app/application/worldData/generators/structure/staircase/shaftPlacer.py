"""
ShaftPlacer — стратегии размещения shaft в пространстве здания.
ТЗ: docs/tz_staircase_generation.md §11

Выбор стратегии по флагам in_a_room / outside:
  in_a_room=False, outside=False → AdjacentShaftPlacer (стандарт)
  in_a_room=True                 → EmbeddedShaftPlacer
  in_a_room=False, outside=True  → EdgeMountedShaftPlacer (TODO)
"""
import logging
from abc import ABC, abstractmethod

from app.dataModel.spatial.facing import (
    Facing, parse_facing, opposite, CARDINAL_FACINGS, INTERCARDINAL_FACINGS,
)
from app.dataModel.structure.building.staircaseSpec import StaircaseSpec, EMBED_AT_CENTER
from app.application.worldData.generators.structure.cellBuilder import _interior
from app.utils.deterministicIds import scoped_rng
from app.application.worldData.generators.structure.layoutEngine import (
    _try_adjacent, _place_next_to_any, _DIRECTIONS,
)
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
logger = logging.getLogger(__name__)


class ShaftPlacer(ABC):
    @abstractmethod
    def place(
        self,
        shaft: _RoomInstance,
        fr_room: _RoomInstance,
        placed_rooms: list[_RoomInstance],
    ) -> bool:
        """Выставляет shaft.origin_x / shaft.origin_y. Возвращает True если успешно."""


class AdjacentShaftPlacer(ShaftPlacer):
    """
    Shaft размещается смежно с fr_room.
    Entry-сторона shaft (opposite(facing)) — сторона, смежная с to_room на верхнем уровне.
    Preferred direction: facing (far end away from fr_room) → shaft прилегает к fr_room с entry-стороны.
    """

    def place(
        self,
        shaft: _RoomInstance,
        fr_room: _RoomInstance,
        placed_rooms: list[_RoomInstance],
    ) -> bool:
        facing = parse_facing(shaft.facing) or Facing.NORTH
        # Entry side = opposite(facing). We want fr_room on the entry side of shaft,
        # i.e. shaft is placed in the facing direction relative to fr_room.
        preferred = facing
        placed_ok = _try_adjacent(shaft, fr_room, preferred, placed_rooms)
        if not placed_ok:
            placed_ok = _place_next_to_any(shaft, placed_rooms)
        if placed_ok:
            logger.info(
                "AdjacentShaftPlacer | shaft=%r placed at (%d,%d) adjacent to fr_room=%r",
                shaft.room_id, shaft.origin_x, shaft.origin_y, fr_room.room_id,
            )
        else:
            logger.error(
                "AdjacentShaftPlacer | shaft=%r: no space adjacent to fr_room=%r",
                shaft.room_id, fr_room.room_id,
            )
        return placed_ok


class EmbeddedShaftPlacer(ShaftPlacer):
    """Embed a shaft on z_lo; runtime metadata identifies its host and entrance."""

    def __init__(self, spec: StaircaseSpec, building_uid: str):
        self.spec = spec
        self.building_uid = building_uid

    def place(self, shaft, fr_room, placed_rooms):
        sc = self.spec
        candidates = [r for r in placed_rooms if r.placed and not r.is_shaft
                      and r.z_offset == shaft.z_offset]
        host = next((r for r in candidates if r.room_id == sc.embed_in), None)
        if host is None:
            logger.error(
                "EmbeddedShaftPlacer | staircase=%r embed_in=%r unavailable on z=%d — largest-room fallback",
                sc.staircase_id, sc.embed_in, shaft.z_offset,
            )
            host = min(candidates, key=lambda r: (-len(r.get_footprint()), r.uid_key)) if candidates else None
        position = sc.embed_at
        if position is None:
            position = scoped_rng(self.building_uid, sc.staircase_id, "embed_at").choice(
                sorted(INTERCARDINAL_FACINGS))
        shaft.embedded_host_key = None
        shaft.embedded_entry = None
        if host is not None:
            if position == EMBED_AT_CENTER:
                shaft.origin_x = host.origin_x + (host.width - shaft.width) // 2
                shaft.origin_y = host.origin_y + (host.depth - shaft.depth) // 2
            else:
                corner = Facing(position)
                east = corner in (Facing.NORTHEAST, Facing.SOUTHEAST)
                north = corner in (Facing.NORTHEAST, Facing.NORTHWEST)
                shaft.origin_x = host.origin_x + (host.width - shaft.width if east else 0)
                shaft.origin_y = host.origin_y + (host.depth - shaft.depth if north else 0)
            fp = shaft.get_footprint()
            host_fp = host.get_footprint()
            interior = _interior(host_fp)
            # Corner footprints may share two outer walls; both inward sides must
            # have walkable host interior beyond them. Center is entirely interior.
            fits = fp <= (interior if position == EMBED_AT_CENTER else host_fp)
            if position == EMBED_AT_CENTER:
                # Leave a floor cell outside each shaft wall, before the host wall.
                padded = fp | {(x + dx, y + dy) for x, y in fp
                               for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))}
                fits = fits and padded <= interior
            fits = fits and shaft.width >= 3 and shaft.depth >= 3
            fits = fits and shaft.width <= host.width - 2 and shaft.depth <= host.depth - 2
            conflicts = any(fp & r.get_footprint() for r in placed_rooms
                            if r.placed and r is not host and r is not shaft
                            and r.z_offset == shaft.z_offset)
            if fits and not conflicts:
                if position == EMBED_AT_CENTER:
                    entry = scoped_rng(self.building_uid, sc.staircase_id, "embed_entry").choice(
                        sorted(CARDINAL_FACINGS))
                else:
                    inward = (Facing.SOUTH if north else Facing.NORTH,
                              Facing.WEST if east else Facing.EAST)
                    facing = parse_facing(shaft.facing)
                    preferred = opposite(facing) if facing is not None else None
                    entry = preferred if preferred in inward else inward[0]
                shaft.embedded_host_key = host.uid_key
                shaft.embedded_entry = entry
                # Stair builders use opposite(facing) for their lower entrance.
                shaft.facing = opposite(entry)
                logger.info("EmbeddedShaftPlacer | shaft=%r host=%r position=%s origin=(%d,%d) entry=%s",
                            shaft.room_id, host.room_id, position, shaft.origin_x, shaft.origin_y, entry)
                return True
        logger.error("EmbeddedShaftPlacer | staircase=%r host=%r: footprint does not fit or overlaps — adjacent fallback",
                     sc.staircase_id, host.room_id if host else None)
        shaft.origin_x = shaft.origin_y = None
        return AdjacentShaftPlacer().place(shaft, fr_room, placed_rooms)


class EdgeMountedShaftPlacer(ShaftPlacer):
    """
    Shaft снаружи здания: entry-сторона прикреплена к внешней стене, три остальные стороны
    (включая facing) — за периметром здания.

    Алгоритм:
      1. Находим внешний край здания в направлении facing по placed_rooms.
      2. Ставим shaft так, чтобы его entry-грань (opposite(facing)) совпала с этим краем.
      3. По оси, перпендикулярной facing, центрируем shaft по fr_room.
      4. Без проверки перекрытий — shaft за периметром, пересечений с interior-комнатами нет.
         Если shaft всё же перекрывает какую-то комнату — логируем WARNING.
    """

    def place(
        self,
        shaft: _RoomInstance,
        fr_room: _RoomInstance,
        placed_rooms: list[_RoomInstance],
    ) -> bool:
        facing = parse_facing(shaft.facing) or Facing.NORTH
        all_placed = [r for r in placed_rooms if r.placed] + [fr_room]

        if facing == Facing.NORTH:
            # Building north exterior = max(y + depth - 1)
            ext = max(r.origin_y + r.depth - 1 for r in all_placed)
            shaft.origin_y = ext                    # shaft south face (entry) at ext
            shaft.origin_x = (fr_room.origin_x
                               + (fr_room.width - shaft.width) // 2)
        elif facing == Facing.SOUTH:
            # Building south exterior = min(y)
            ext = min(r.origin_y for r in all_placed)
            shaft.origin_y = ext - shaft.depth + 1  # shaft north face (entry) at ext
            shaft.origin_x = (fr_room.origin_x
                               + (fr_room.width - shaft.width) // 2)
        elif facing == Facing.EAST:
            # Building east exterior = max(x + width - 1)
            ext = max(r.origin_x + r.width - 1 for r in all_placed)
            shaft.origin_x = ext                    # shaft west face (entry) at ext
            shaft.origin_y = (fr_room.origin_y
                               + (fr_room.depth - shaft.depth) // 2)
        else:  # west
            # Building west exterior = min(x)
            ext = min(r.origin_x for r in all_placed)
            shaft.origin_x = ext - shaft.width + 1  # shaft east face (entry) at ext
            shaft.origin_y = (fr_room.origin_y
                               + (fr_room.depth - shaft.depth) // 2)

        # Sanity: warn if shaft overlaps any interior room
        shaft_fp = shaft.get_footprint()
        for r in placed_rooms:
            if r.placed and r is not shaft and shaft_fp & r.get_footprint():
                logger.warning(
                    "EdgeMountedShaftPlacer | shaft=%r overlaps room=%r — "
                    "outside=True requires fr_room at building exterior",
                    shaft.room_id, r.room_id,
                )

        logger.info(
            "EdgeMountedShaftPlacer | shaft=%r placed at (%d,%d) outside building "
            "(facing=%r, ext_coord=%d)",
            shaft.room_id, shaft.origin_x, shaft.origin_y, facing, ext,
        )
        return True


def make_shaft_placer(sc: StaircaseSpec, *, building_uid: str = "") -> ShaftPlacer:
    """Выбирает стратегию по флагам записи staircases[]."""
    if sc.in_a_room:
        return EmbeddedShaftPlacer(sc, building_uid)
    if sc.outside:
        return EdgeMountedShaftPlacer()
    return AdjacentShaftPlacer()
