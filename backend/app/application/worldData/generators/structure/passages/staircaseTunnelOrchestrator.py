"""
Оркестратор соединения якоря лестницы с целевой комнатой.

Стратегия выбирается по контексту:
  anchor смежен с footprint  → archway (floor+open, без двери)
  не смежен, level.z >= 0   → SurfaceCorridorBuilder (наземный коридор)
  не смежен, level.z <  0   → UndergroundTunnelBuilder (подземный тоннель)
"""
from __future__ import annotations

import logging

from app.dataModel.locations.transitions.transitionType import TransitionType
from app.application.worldData.generators.structure.passages.wallBreachPlacer import WallBreachPlacer
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase.surfaceCorridor import SurfaceCorridorBuilder
from app.application.worldData.generators.structure.staircase.undergroundTunnel import UndergroundTunnelBuilder
from app.db.models.locationLevel import LocationLevel
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.application.worldData.generators.structure.physicalTransition import physical_transition, level_endpoint

logger = logging.getLogger(__name__)

_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


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
        ground_z:       int = 0,
    ) -> None:
        self.cells          = cells
        self.world_uid      = world_uid
        self.building_uid   = building_uid
        self.mat            = mat
        self.z_top          = z_top
        self.conn_label     = conn_label
        self.passage_height = passage_height
        self.ground_z       = ground_z

    def connect(
        self,
        anchor: tuple[int, int],
        room:   _RoomInstance,
        level:  LocationLevel,
        sc_id:  str = "?",
    ) -> Transition | None:
        room_fp = set(room.get_footprint())

        for dx, dy in _NEIGHBORS:
            wall_cell = (anchor[0] + dx, anchor[1] + dy)
            if wall_cell in room_fp:
                return self._archway(anchor, wall_cell, room, level, sc_id)

        if level.z >= self.ground_z:
            return self._surface(anchor, room, level, sc_id)
        return self._underground(anchor, room, level, sc_id)

    def _archway(
        self,
        anchor:    tuple[int, int],
        wall_cell: tuple[int, int],
        room:      _RoomInstance,
        level:     LocationLevel,
        sc_id:     str,
    ) -> Transition:
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
        return physical_transition(self.world_uid, TransitionType.ARCHWAY, level_endpoint(level, wx, wy, self.building_uid), level_endpoint(level, anchor[0], anchor[1], self.building_uid), self.building_uid)

    def _surface(
        self,
        anchor: tuple[int, int],
        room:   _RoomInstance,
        level:  LocationLevel,
        sc_id:  str,
    ) -> Transition | None:
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
    ) -> Transition | None:
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
        return physical_transition(self.world_uid, TransitionType.DOORWAY, level_endpoint(level, bx, by, self.building_uid), level_endpoint(level, anchor[0], anchor[1], self.building_uid), self.building_uid)
