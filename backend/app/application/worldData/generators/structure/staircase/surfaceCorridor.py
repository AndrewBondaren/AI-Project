"""
Surface corridor — соединяет внешний якорь лестницы с верхней комнатой на уровне z_top.
Аналог UndergroundTunnelBuilder, но работает горизонтально на поверхности.
ТЗ: docs/tz_staircase_generation.md §8.1
"""
from __future__ import annotations

import logging
import uuid

from app.dataModel.structure.enums.buildingElement import StructureElement
from app.application.worldData.generators.structure.cellBuilder import _interior, _wall_cell
from app.application.worldData.generators.structure.cellFactory import _floor_cell, _open_cell
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.dataModel.structure.enums.passageType import PassageType
from app.application.worldData.generators.structure.passages.wallBreachPlacer import WallBreachPlacer
from app.application.worldData.generators.structure.passages.tunnelPathFinder import TunnelPathFinder
from app.application.worldData.generators.structure.staircase.undergroundTunnel import _VEC_TO_FACING
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage

logger = logging.getLogger(__name__)



def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


class SurfaceCorridorBuilder:
    """
    Строит 1-ячеечный наземный коридор от внешнего якоря до верхней комнаты.

    Использование:
        SurfaceCorridorBuilder(cells, world_uid, building_uid, mat,
                               z_top, conn_label=..., passage_height=...).build(
            anchor, to_room, to_level, building_uid, sc_id)
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

    def build(
        self,
        anchor:   tuple[int, int],
        to_room:  _RoomInstance,
        to_level: LocationLevel,
        sc_id:    str = "?",
    ) -> LocationPassage | None:
        to_fp = set(to_room.get_footprint())

        if anchor in to_fp:
            return None

        occupied_top = {(x, y) for (x, y, z) in self.cells if z == self.z_top}
        blocked = occupied_top - to_fp

        to_interior = {
            (x, y)
            for (x, y, z), cell in self.cells.items()
            if z == self.z_top
            and (x, y) in to_fp
            and cell.system_building_element != StructureElement.WALL
        }
        target = to_interior if to_interior else to_fp

        path = TunnelPathFinder().find_path(anchor, target, blocked)
        if len(path) < 2:
            logger.error(
                "surface_corridor %s: путь не найден от %s до комнаты %r",
                self.conn_label, anchor, to_room.room_id,
            )
            return None

        wall_cell_xy = self._place_corridor(path, to_fp)

        wx, wy = wall_cell_xy if wall_cell_xy else path[-1]
        passage_uid = _det_uuid(self.building_uid, "surface_corridor", sc_id, to_room.room_id)
        return LocationPassage(
            passage_uid=passage_uid,
            world_uid=self.world_uid,
            from_level_uid=to_level.level_uid,
            from_x=anchor[0],
            from_y=anchor[1],
            to_level_uid=to_level.level_uid,
            to_x=wx,
            to_y=wy,
            system_passage_type=PassageType.ARCHWAY,
            is_bidirectional=True,
        )

    def _place_corridor(
        self,
        path:  list[tuple[int, int]],
        to_fp: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        """
        path[0]    = внешний якорь (лестница уже размещена, добавляем только стены)
        path[1..-3]= коридорный пол на z_top
        path[-2]   = пролом в стене верхней комнаты
        path[-1]   = первая внутренняя ячейка верхней комнаты
        """
        path_set_2d = {(x, y) for x, y in path}
        wu, bu, mat = self.world_uid, self.building_uid, self.mat

        def _floor_open(x: int, y: int) -> None:
            if (x, y, self.z_top) not in self.cells:
                self.cells[(x, y, self.z_top)] = _floor_cell(x, y, self.z_top, wu, bu, mat)
            for z in range(self.z_top + 1, self.z_top + self.passage_height):
                if (x, y, z) not in self.cells:
                    self.cells[(x, y, z)] = _open_cell(x, y, z, wu, bu, mat)

        def _side_walls(x: int, y: int, skip: tuple[int, int] | None = None) -> None:
            for ddx in (-1, 0, 1):
                for ddy in (-1, 0, 1):
                    if ddx == 0 and ddy == 0:
                        continue
                    nx, ny = x + ddx, y + ddy
                    if (nx, ny) == skip:
                        continue
                    if (nx, ny) in path_set_2d or (nx, ny) in to_fp:
                        continue
                    for z in range(self.z_top, self.z_top + self.passage_height):
                        if (nx, ny, z) not in self.cells:
                            self.cells[(nx, ny, z)] = _wall_cell(nx, ny, z, wu, bu, mat)

        ax, ay = path[0]
        _side_walls(ax, ay, skip=path[1] if len(path) > 1 else None)

        breach_xy: tuple[int, int] | None = None

        if len(path) >= 3:
            for x, y in path[1:-2]:
                _floor_open(x, y)
                _side_walls(x, y)

            bx, by = path[-2]
            px, py = path[-3]
            facing = _VEC_TO_FACING[(bx - px, by - py)]
            WallBreachPlacer(self.cells, wu, bu).place_for_corridor(
                bx, by, self.z_top, self.z_top + self.passage_height,
                mat, facing, self.passage_height, self.conn_label,
            )
            _side_walls(bx, by)
            breach_xy = (bx, by)
        else:
            logger.warning(
                "surface_corridor %s: путь слишком короткий (%d ячеек), пролом не размещён",
                self.conn_label, len(path),
            )

        ex, ey = path[-1]
        if (ex, ey, self.z_top) not in self.cells:
            self.cells[(ex, ey, self.z_top)] = _floor_cell(ex, ey, self.z_top, wu, bu, mat)
        _side_walls(ex, ey)

        logger.info(
            "surface_corridor %s: %d ячеек от %s до %s (z=%d)",
            self.conn_label, len(path) - 1, path[0], path[-1], self.z_top,
        )
        return breach_xy
