"""
Vertical ladder builder — люк/лестница для перехода поверхность ↔ подземный уровень.
ТЗ: docs/tz_staircase_generation.md §8
"""
from __future__ import annotations

import logging

from app.application.worldData.generators.structure.cellBuilder import _wall_cell
from app.application.worldData.generators.structure.cellFactory import _ladder_cell, _trapdoor_cell, _window_cell
from app.application.worldData.generators.structure.staircase.base import StaircaseBuilder
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadderHelper import (
    VerticalLadderParams,
    _FACING_VEC,
    _NEIGHBORS,
    _compute_vertical_ladder_params,
)
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadderValidator import (
    VerticalLadderValidator,
)

logger = logging.getLogger(__name__)


def _place_enclosure_walls(
    ax: int, ay: int,
    z_lo: int, z_top: int,
    facing: str | None,
    world_uid: str, building_uid: str, mat: str,
    cells: dict,
    open_wall_shaft: str | None = None,
) -> None:
    """
    Стены вокруг столба лестницы — 3 стороны, кроме entry (сторона здания).
    entry = направление, противоположное facing.
    Если facing не задан — закрываем все 4 стороны.
    open_wall_shaft — материал окна; если задан, стены заменяются окнами.
    """
    facing_vec = _FACING_VEC.get(facing) if facing else None
    entry_vec  = (-facing_vec[0], -facing_vec[1]) if facing_vec else None

    for dx, dy in _NEIGHBORS:
        if (dx, dy) == entry_vec:
            continue  # эту сторону прорубит edge_ladder_passage
        wx, wy = ax + dx, ay + dy
        for z in range(z_lo, z_top):
            if (wx, wy, z) not in cells:
                if open_wall_shaft:
                    cells[(wx, wy, z)] = _window_cell(wx, wy, z, world_uid, building_uid, open_wall_shaft)
                else:
                    cells[(wx, wy, z)] = _wall_cell(wx, wy, z, world_uid, building_uid, mat)


class VerticalLadderBuilder(StaircaseBuilder):
    _validator = VerticalLadderValidator()

    def _build_fixed(
        self,
        params: VerticalLadderParams,
    ) -> tuple[set[tuple[int, int, int]], tuple[int, int], tuple[int, int]]:
        ax, ay = params.anchor
        path_set: set[tuple[int, int, int]] = set()

        for z in range(self.z_lo, self.z_top):
            self.cells[(ax, ay, z)] = _ladder_cell(ax, ay, z, self.world_uid, self.building_uid, self.mat)
            path_set.add((ax, ay, z))

        if params.has_trapdoor:
            self.cells[(ax, ay, self.z_top)] = _trapdoor_cell(
                ax, ay, self.z_top, self.world_uid, self.building_uid, self.mat,
            )

        if params.has_walls:
            _place_enclosure_walls(
                ax, ay, self.z_lo, self.z_top, params.facing,
                self.world_uid, self.building_uid, self.mat, self.cells,
                open_wall_shaft=params.open_wall_shaft,
            )

        extras = []
        if params.has_trapdoor: extras.append("+trapdoor")
        if params.has_walls:    extras.append("+walls")
        logger.info(
            "vertical_ladder %s  fixed (%d,%d) z=%d..%d%s",
            self.conn_label, ax, ay, self.z_lo, self.z_top - 1,
            (" " + " ".join(extras)) if extras else "",
        )
        return path_set, (ax, ay), (ax, ay)

    def _build_movable(
        self,
        params: VerticalLadderParams,
    ) -> tuple[set[tuple[int, int, int]], tuple[int, int], tuple[int, int]]:
        raise NotImplementedError(f"vertical_ladder {self.conn_label}: movable not implemented")

    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        entry        = self.sc_entry or {}
        is_movable   = entry.get("is_movable",   False)
        has_trapdoor = entry.get("has_trapdoor", False)
        near_wall    = entry.get("near_wall",    False)
        on_the_edge  = entry.get("on_the_edge",  False)
        has_walls        = entry.get("has_walls",        False)
        facing           = entry.get("facing",           None)
        open_wall_shaft  = entry.get("open_wall_shaft",  None)

        params = _compute_vertical_ladder_params(
            self.fr, self.to,
            cells=self.cells, z_lo=self.z_lo,
            is_movable=is_movable, has_trapdoor=has_trapdoor,
            near_wall=near_wall, on_the_edge=on_the_edge,
            has_walls=has_walls, facing=facing,
            open_wall_shaft=open_wall_shaft,
        )

        if params.is_movable:
            path_set, fr_anchor, to_anchor = self._build_movable(params)
        else:
            path_set, fr_anchor, to_anchor = self._build_fixed(params)

        self.path_set = path_set

        self._validator.validate(
            fr_anchor=fr_anchor,
            to_anchor=to_anchor,
            z_lo=self.z_lo,
            z_top=self.z_top,
            cells=self.cells,
            conn_label=self.conn_label,
            fr_footprint=set(self.fr.get_footprint()),
            to_footprint=set(self.to.get_footprint()),
            on_the_edge=on_the_edge,
            is_movable=is_movable,
            has_trapdoor=has_trapdoor,
        )

        return fr_anchor, to_anchor
