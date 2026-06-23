from __future__ import annotations

import math

from app.application.worldData.generators.structure.cellFactory import _roof_cell
from app.db.models.mapCell import MapCell


def _shrink_roof_loop(
    footprint: set[tuple[int, int]],
    top_z: int,
    x_min: int, x_max: int,
    y_min: int, y_max: int,
    shrink_x: bool,
    shrink_y: bool,
    slope: float,
    wu: str, bu: str, mat: str,
) -> list[MapCell]:
    """
    Shared shrink loop for gable (one axis) and hull (both axes) roofs.

    shrink_x / shrink_y control which axes collapse per z-unit.
    slope_step must be > 0 (caller is responsible).
    """
    widths = []
    if shrink_x:
        widths.append(x_max - x_min + 1)
    if shrink_y:
        widths.append(y_max - y_min + 1)
    half = min(widths) / 2
    peak = math.ceil(half / slope)

    result: list[MapCell] = []
    for dz in range(peak + 1):
        shrink = int(dz * slope)
        x_lo = x_min + shrink if shrink_x else x_min
        x_hi = x_max - shrink if shrink_x else x_max
        y_lo = y_min + shrink if shrink_y else y_min
        y_hi = y_max - shrink if shrink_y else y_max
        if x_lo > x_hi or y_lo > y_hi:
            break
        for x, y in footprint:
            if x_lo <= x <= x_hi and y_lo <= y <= y_hi:
                result.append(_roof_cell(x, y, top_z + dz, wu, bu, mat))
    return result


class GableRoof:
    """
    Gable (двускатная) roof.

    Shrinks the footprint along the short axis by slope_step per z-unit.
    The ridge runs parallel to the long axis.

    slope_step=1.0 → 45°.
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
        if self.slope_step <= 0:
            raise ValueError(f"slope_step must be > 0, got {self.slope_step}")

        xs = [x for x, _ in footprint]
        ys = [y for _, y in footprint]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        w = x_max - x_min + 1
        h = y_max - y_min + 1
        wu, bu, mat = self.world_uid, self.building_uid, self.material

        if w >= h:
            return _shrink_roof_loop(
                footprint, top_z, x_min, x_max, y_min, y_max,
                shrink_x=False, shrink_y=True, slope=self.slope_step,
                wu=wu, bu=bu, mat=mat,
            )
        return _shrink_roof_loop(
            footprint, top_z, x_min, x_max, y_min, y_max,
            shrink_x=True, shrink_y=False, slope=self.slope_step,
            wu=wu, bu=bu, mat=mat,
        )
