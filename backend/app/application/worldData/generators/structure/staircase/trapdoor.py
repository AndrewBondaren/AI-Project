"""
Trapdoor builder — 1×1 люк в полу для перехода поверхность ↔ подземный уровень.
"""
from app.application.worldData.generators.structure.cellFactory import _trapdoor_cell
from app.application.worldData.generators.structure.staircase.base import (
    StaircaseBuilder, sw_anchor,
)


class TrapdoorBuilder(StaircaseBuilder):
    def build(self) -> tuple[tuple[int, int], tuple[int, int]]:
        fr_anchor = sw_anchor(self.fr)
        to_anchor = sw_anchor(self.to)
        fx, fy = fr_anchor
        tx, ty = to_anchor

        self.cells[(fx, fy, self.fr_level.z)] = _trapdoor_cell(
            fx, fy, self.fr_level.z, self.world_uid, self.building_uid, self.mat
        )
        for z_layer in range(self.to_level.z, self.to_level.z + self.to_level.z_height):
            self.cells[(tx, ty, z_layer)] = _trapdoor_cell(
                tx, ty, z_layer, self.world_uid, self.building_uid, self.mat
            )

        return fr_anchor, to_anchor
