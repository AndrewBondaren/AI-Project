"""
Подземный тоннель — соединяет якорь лестницы с нижней комнатой при z_lo < 0.
ТЗ: docs/tz_staircase_generation.md §8.1

Используется любым staircase-builder'ом, у которого якорь оказывается
снаружи footprint нижней комнаты на подземном уровне.
"""
from __future__ import annotations

import logging

from app.application.worldData.generators.structure.cellBuilder import _wall_cell
from app.application.worldData.generators.structure.cellFactory import _floor_cell, _open_cell
from app.application.worldData.generators.structure.heightChecker import PassageHeightChecker
from app.application.worldData.generators.utils.facing import Facing
from app.application.worldData.generators.structure.passages.wallBreachPlacer import WallBreachPlacer
from app.application.worldData.generators.structure.passages.tunnelPathFinder import TunnelPathFinder

logger = logging.getLogger(__name__)

_VEC_TO_FACING: dict[tuple[int, int], Facing] = {
    (1,  0): Facing.EAST,
    (-1, 0): Facing.WEST,
    (0,  1): Facing.NORTH,
    (0, -1): Facing.SOUTH,
}


class UndergroundTunnelBuilder:
    """
    Строит 1-ячеечный подземный тоннель от anchor до footprint нижней комнаты.

    Использование:
        UndergroundTunnelBuilder(cells, world_uid, building_uid, mat,
                                 z_lo, z_top, conn_label).build(anchor, fr_fp)
    """

    def __init__(
        self,
        cells:          dict,
        world_uid:      str,
        building_uid:   str,
        mat:            str,
        z_lo:           int,
        z_top:          int,
        *,
        conn_label:     str = "?",
        passage_height: int,
    ) -> None:
        self.cells          = cells
        self.world_uid      = world_uid
        self.building_uid   = building_uid
        self.mat            = mat
        self.z_lo           = z_lo
        self.z_top          = z_top
        self.conn_label     = conn_label
        self.passage_height = passage_height

    def build(
        self,
        anchor: tuple[int, int],
        fr_fp:  set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        """
        Строит тоннель от anchor до fr_fp.

        Вызывать только при z_lo < 0 и anchor ∉ fr_fp.
        Возвращает координаты ячейки пролома (bx, by) или None если тоннель не построен.
        """
        if anchor in fr_fp:
            return None

        anchor_shell = {
            (anchor[0] + dx, anchor[1] + dy)
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
            if not (dx == 0 and dy == 0)
        }

        blocked = {
            (x, y)
            for (x, y, z), cell in self.cells.items()
            if z == self.z_lo
            and cell.system_building_element == "wall"
            and (x, y) not in fr_fp
            and (x, y) not in anchor_shell
        }

        # Целимся во внутренние (не-стеновые) ячейки нижней комнаты, чтобы путь
        # проходил сквозь периметральную стену, а не упирался в неё.
        fr_interior = {
            (x, y)
            for (x, y, z), cell in self.cells.items()
            if z == self.z_lo
            and (x, y) in fr_fp
            and cell.system_building_element != "wall"
        }
        target = fr_interior if fr_interior else fr_fp

        path = TunnelPathFinder().find_path(anchor, target, blocked)
        if len(path) < 2:
            logger.error(
                "underground_tunnel %s: путь не найден от %s до нижней комнаты",
                self.conn_label, anchor,
            )
            return None

        return self._place_tunnel(path, fr_fp)

    def _place_tunnel(
        self,
        path:  list[tuple[int, int]],
        fr_fp: set[tuple[int, int]],
    ) -> tuple[int, int] | None:
        """
        path[0]    = anchor лестницы (shaft-ячейки уже размещены, стены добавляем)
        path[1..-3]= тоннельный пол
        path[-2]   = пролом в стене нижней комнаты → дверь
        path[-1]   = первая внутренняя ячейка нижней комнаты → floor
        """
        path_set_2d = {(x, y) for x, y in path}
        wu, bu, mat = self.world_uid, self.building_uid, self.mat

        checker = PassageHeightChecker(self.cells, self.passage_height)

        def _fits(h: int) -> bool:
            return all(checker.fits_column(x, y, self.z_lo + 1, h - 1) for x, y in path[1:])

        actual_height = (
            self.passage_height if _fits(self.passage_height) else checker.min_height
        )

        def _floor_open(x: int, y: int) -> None:
            self.cells[(x, y, self.z_lo)] = _floor_cell(x, y, self.z_lo, wu, bu, mat)
            for z in range(self.z_lo + 1, self.z_lo + actual_height):
                self.cells[(x, y, z)] = _open_cell(x, y, z, wu, bu, mat)

        wall_breach_placer = WallBreachPlacer(self.cells, wu, bu)

        def _side_walls(x: int, y: int) -> None:
            for ddx in (-1, 0, 1):
                for ddy in (-1, 0, 1):
                    if ddx == 0 and ddy == 0:
                        continue
                    nx, ny = x + ddx, y + ddy
                    if (nx, ny) in path_set_2d or (nx, ny) in fr_fp:
                        continue
                    for z in range(self.z_lo, self.z_lo + actual_height):
                        if (nx, ny, z) not in self.cells:
                            self.cells[(nx, ny, z)] = _wall_cell(nx, ny, z, wu, bu, mat)

        # Якорь — только стены (shaft-ячейки не трогаем)
        ax, ay = path[0]
        _side_walls(ax, ay)

        breach_xy: tuple[int, int] | None = None

        if len(path) >= 3:
            # Тоннельный пол
            for x, y in path[1:-2]:
                _floor_open(x, y)
                _side_walls(x, y)

            # Дверь на пролом в стене нижней комнаты
            bx, by = path[-2]
            px, py = path[-3]
            facing = _VEC_TO_FACING[(bx - px, by - py)]
            wall_breach_placer.place_for_corridor(bx, by, self.z_lo, self.z_lo + actual_height, mat, facing, actual_height, self.conn_label)
            _side_walls(bx, by)
            breach_xy = (bx, by)
        else:
            # Якорь прямо у стены — дверь поставить некуда
            logger.warning(
                "underground_tunnel %s: путь слишком короткий (%d ячеек), дверь не размещена",
                self.conn_label, len(path),
            )

        # Первая внутренняя ячейка нижней комнаты — только пол на z_lo,
        # выше — implicit open air внутри комнаты (open_cell не нужен).
        ex, ey = path[-1]
        self.cells[(ex, ey, self.z_lo)] = _floor_cell(ex, ey, self.z_lo, wu, bu, mat)
        _side_walls(ex, ey)

        logger.info(
            "underground_tunnel %s: %d ячеек от %s до %s (z=%d..%d)",
            self.conn_label, len(path) - 1, path[0], path[-1], self.z_lo, self.z_top - 1,
        )
        return breach_xy
