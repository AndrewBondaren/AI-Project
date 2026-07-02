"""
Vertical ladder builder — люк/лестница для перехода поверхность ↔ подземный уровень.
ТЗ: docs/tz_staircase_generation.md §8
"""
from __future__ import annotations

import logging

from app.dataModel.spatial.facing import parse_facing
from app.application.worldData.generators.structure.cellFactory import (
    _floor_cell, _ladder_cell, _trapdoor_cell,
)
from app.application.worldData.generators.structure.staircase.base import StaircaseBuilder
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadderHelper import (
    VerticalLadderParams,
    _compute_vertical_ladder_params,
)
from app.application.worldData.generators.structure.staircase.verticalLadder.verticalLadderValidator import (
    VerticalLadderValidator,
)

logger = logging.getLogger(__name__)


class VerticalLadderBuilder(StaircaseBuilder):
    _validator = VerticalLadderValidator()

    @property
    def _on_the_edge(self) -> bool:
        return (self.sc_entry or {}).get("on_the_edge", False)

    def _build_fixed(
        self,
        params: VerticalLadderParams,
        on_the_edge: bool,
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
        else:
            self.cells.setdefault(
                (ax, ay, self.z_top),
                _floor_cell(ax, ay, self.z_top, self.world_uid, self.building_uid, self.mat),
            )

        place_walls = params.has_walls or (on_the_edge and self.z_lo < 0)
        if place_walls:
            if params.closed_exit:
                z_hi = self.z_top + self.to_level.z_height
                self._place_shaft_enclosure_closed({(ax, ay)}, z_hi=z_hi, open_wall_shaft=params.open_wall_shaft)
            else:
                self._place_shaft_enclosure({(ax, ay)}, open_wall_shaft=params.open_wall_shaft)

        extras = []
        if params.has_trapdoor: extras.append("+trapdoor")
        if place_walls:         extras.append("+walls")
        logger.info(
            "vertical_ladder %s  fixed (%d,%d) z=%d..%d%s",
            self.conn_label, ax, ay, self.z_lo, self.z_top - 1,
            (" " + " ".join(extras)) if extras else "",
        )
        return path_set, (ax, ay), (ax, ay)

    def _build_movable(
        self,
        params: VerticalLadderParams,
        on_the_edge: bool,
    ) -> tuple[set[tuple[int, int, int]], tuple[int, int], tuple[int, int]]:
        raise NotImplementedError(f"vertical_ladder {self.conn_label}: movable not implemented")

    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        entry        = self.sc_entry or {}
        is_movable   = entry.get("is_movable",   False)
        has_trapdoor = entry.get("has_trapdoor", False)
        near_wall    = entry.get("near_wall",    False)
        on_the_edge  = self._on_the_edge
        has_walls        = entry.get("has_walls",        False)
        facing           = parse_facing(entry.get("facing", None))
        open_wall_shaft  = entry.get("open_wall_shaft",  None)
        closed_exit      = entry.get("closed_exit",      False)

        params = _compute_vertical_ladder_params(
            self.fr, self.to,
            cells=self.cells, z_lo=self.z_lo, z_top=self.z_top,
            is_movable=is_movable, has_trapdoor=has_trapdoor,
            near_wall=near_wall, on_the_edge=on_the_edge,
            passage_height=self.passage_height,
            has_walls=has_walls, facing=facing,
            open_wall_shaft=open_wall_shaft, closed_exit=closed_exit,
        )

        if params.is_movable:
            path_set, fr_anchor, to_anchor = self._build_movable(params, on_the_edge)
        else:
            path_set, fr_anchor, to_anchor = self._build_fixed(params, on_the_edge)

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
            passage_height=self.passage_height,
        )

        return fr_anchor, to_anchor
