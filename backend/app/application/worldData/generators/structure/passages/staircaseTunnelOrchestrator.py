"""
Оркестратор соединения якоря лестницы с целевой комнатой.

Стратегия выбирается по контексту:
  anchor смежен с footprint  → archway (floor+open, без двери)
  не смежен, level.z >= 0   → SurfaceCorridorBuilder (наземный коридор)
  не смежен, level.z <  0   → UndergroundTunnelBuilder (подземный тоннель)
"""
from __future__ import annotations

import logging
import uuid

from app.application.worldData.generators.structure.passages.passageType import PassageType
from app.application.worldData.generators.structure.passages.wallBreachPlacer import WallBreachPlacer
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase.surfaceCorridor import SurfaceCorridorBuilder
from app.application.worldData.generators.structure.staircase.undergroundTunnel import UndergroundTunnelBuilder
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage

logger = logging.getLogger(__name__)

_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


class StaircaseTunnelOrchestrator:
    """
    Соединяет якорь лестницы с комнатой, выбирая стратегию по контексту.

    z_top — z верхней комнаты лестницы (передаётся в UndergroundTunnelBuilder для логирования).
    """

    def __init__(
        self,
        cells:          dict,
        world_uid:      str,
        building_uid:   str,
        mat:            str,
        z_top:          int,
        *,
        conn_label:     str = "?",
        passage_height: int,
    ) -> None:
        self.cells          = cells
        self.world_uid      = world_uid
        self.building_uid   = building_uid
        self.mat            = mat
        self.z_top          = z_top
        self.conn_label     = conn_label
        self.passage_height = passage_height

    def connect(
        self,
        anchor: tuple[int, int],
        room:   _RoomInstance,
        level:  LocationLevel,
        sc_id:  str = "?",
    ) -> LocationPassage | None:
        room_fp = set(room.get_footprint())

        for dx, dy in _NEIGHBORS:
            wall_cell = (anchor[0] + dx, anchor[1] + dy)
            if wall_cell in room_fp:
                return self._archway(anchor, wall_cell, room, level, sc_id)

        if level.z >= 0:
            return self._surface(anchor, room, level, sc_id)
        return self._underground(anchor, room, level, sc_id)

    def _archway(
        self,
        anchor:    tuple[int, int],
        wall_cell: tuple[int, int],
        room:      _RoomInstance,
        level:     LocationLevel,
        sc_id:     str,
    ) -> LocationPassage:
        wx, wy = wall_cell
        z_lo   = level.z
        z_hi   = level.z + level.z_height
        WallBreachPlacer(self.cells, self.world_uid, self.building_uid).place_for_archway(
            wx, wy, z_lo, z_hi, self.mat,
        )
        logger.info(
            "tunnel_orchestrator %r: archway at (%d,%d) z=%d..%d (anchor=%s, room=%r)",
            sc_id, wx, wy, z_lo, z_hi - 1, anchor, room.room_id,
        )
        passage_uid = _det_uuid(self.building_uid, "archway", sc_id, room.room_id)
        return LocationPassage(
            passage_uid=passage_uid,
            world_uid=self.world_uid,
            from_level_uid=level.level_uid,
            from_x=wx,
            from_y=wy,
            to_level_uid=level.level_uid,
            to_x=anchor[0],
            to_y=anchor[1],
            system_passage_type=PassageType.ARCHWAY,
            is_bidirectional=True,
        )

    def _surface(
        self,
        anchor: tuple[int, int],
        room:   _RoomInstance,
        level:  LocationLevel,
        sc_id:  str,
    ) -> LocationPassage | None:
        return SurfaceCorridorBuilder(
            cells=self.cells,
            world_uid=self.world_uid,
            building_uid=self.building_uid,
            mat=self.mat,
            z_top=level.z,
            conn_label=self.conn_label,
            passage_height=self.passage_height,
        ).build(anchor, room, level, sc_id=sc_id)

    def _underground(
        self,
        anchor: tuple[int, int],
        room:   _RoomInstance,
        level:  LocationLevel,
        sc_id:  str,
    ) -> LocationPassage | None:
        breach_xy = UndergroundTunnelBuilder(
            cells=self.cells,
            world_uid=self.world_uid,
            building_uid=self.building_uid,
            mat=self.mat,
            z_lo=level.z,
            z_top=self.z_top,
            conn_label=self.conn_label,
            passage_height=self.passage_height,
        ).build(anchor, set(room.get_footprint()))

        if breach_xy is None:
            return None

        bx, by = breach_xy
        passage_uid = _det_uuid(self.building_uid, "underground_tunnel", sc_id, room.room_id)
        return LocationPassage(
            passage_uid=passage_uid,
            world_uid=self.world_uid,
            from_level_uid=level.level_uid,
            from_x=bx,
            from_y=by,
            to_level_uid=level.level_uid,
            to_x=anchor[0],
            to_y=anchor[1],
            system_passage_type=PassageType.DOORWAY,
            is_bidirectional=True,
        )
