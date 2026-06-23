from __future__ import annotations

import math

from app.application.worldData.generators.structure.structureElement import StructureElement
from app.db.models.mapCell import MapCell


def _roof_cell(x: int, y: int, z: int, world_uid: str, building_uid: str, material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element=StructureElement.ROOF,
        system_material=material,
        is_structural=True,
        location_uid=building_uid,
    )


class GableRoof:
    """
    Gable (двускатная) roof.

    Shrinks the footprint along the short axis by slope_step per z-unit.
    The ridge runs parallel to the long axis.

    slope_step=1.0 → 45° slope.
    """

    def __init__(
        self,
        world_uid: str,
        building_uid: str,
        material: str,
        slope_step: float = 1.0,
    ) -> None:
        self.world_uid    = world_uid
        self.building_uid = building_uid
        self.material     = material
        self.slope_step   = slope_step

    def build(self, footprint: set[tuple[int, int]], top_z: int) -> list[MapCell]:
        if not footprint:
            return []

        xs = [x for x, _ in footprint]
        ys = [y for _, y in footprint]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        w = x_max - x_min + 1
        h = y_max - y_min + 1

        wu, bu, mat = self.world_uid, self.building_uid, self.material
        slope = self.slope_step
        result: list[MapCell] = []

        if w >= h:
            # ridge along X axis — shrink Y
            half = h / 2
            peak = math.ceil(half / slope)
            for dz in range(peak + 1):
                shrink = int(dz * slope)
                y_lo = y_min + shrink
                y_hi = y_max - shrink
                if y_lo > y_hi:
                    break
                for x, y in footprint:
                    if y_lo <= y <= y_hi:
                        result.append(_roof_cell(x, y, top_z + dz, wu, bu, mat))
        else:
            # ridge along Y axis — shrink X
            half = w / 2
            peak = math.ceil(half / slope)
            for dz in range(peak + 1):
                shrink = int(dz * slope)
                x_lo = x_min + shrink
                x_hi = x_max - shrink
                if x_lo > x_hi:
                    break
                for x, y in footprint:
                    if x_lo <= x <= x_hi:
                        result.append(_roof_cell(x, y, top_z + dz, wu, bu, mat))

        return result
