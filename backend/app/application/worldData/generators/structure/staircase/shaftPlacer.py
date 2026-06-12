"""
ShaftPlacer — стратегии размещения shaft в пространстве здания.
ТЗ: docs/tz_staircase_generation.md §11

Выбор стратегии по флагам in_a_room / outside:
  in_a_room=False, outside=False → AdjacentShaftPlacer (стандарт)
  in_a_room=True                 → EmbeddedShaftPlacer (TODO)
  in_a_room=False, outside=True  → EdgeMountedShaftPlacer (TODO)
"""
import logging
from abc import ABC, abstractmethod

from app.application.worldData.generators.structure.layoutEngine import (
    _try_adjacent, _place_next_to_any, _DIRECTIONS,
)
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
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
        facing = shaft.facing or "north"
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
    """Shaft embedded внутри embed_in комнаты. TODO: step 12."""

    def place(self, shaft, fr_room, placed_rooms):
        raise NotImplementedError("EmbeddedShaftPlacer not yet implemented")


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
        facing = shaft.facing or "north"
        all_placed = [r for r in placed_rooms if r.placed] + [fr_room]

        if facing == "north":
            # Building north exterior = max(y + depth - 1)
            ext = max(r.origin_y + r.depth - 1 for r in all_placed)
            shaft.origin_y = ext                    # shaft south face (entry) at ext
            shaft.origin_x = (fr_room.origin_x
                               + (fr_room.width - shaft.width) // 2)
        elif facing == "south":
            # Building south exterior = min(y)
            ext = min(r.origin_y for r in all_placed)
            shaft.origin_y = ext - shaft.depth + 1  # shaft north face (entry) at ext
            shaft.origin_x = (fr_room.origin_x
                               + (fr_room.width - shaft.width) // 2)
        elif facing == "east":
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


def make_shaft_placer(sc_entry: dict) -> ShaftPlacer:
    """Выбирает стратегию по флагам sc_entry."""
    in_a_room = sc_entry.get("in_a_room", False)
    outside = sc_entry.get("outside", False)
    if in_a_room:
        return EmbeddedShaftPlacer()
    if outside:
        return EdgeMountedShaftPlacer()
    return AdjacentShaftPlacer()
