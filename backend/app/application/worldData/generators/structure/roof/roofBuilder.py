from __future__ import annotations

import math

from app.application.worldData.generators.structure.roof.gableRoof import GableRoof, _roof_cell
from app.application.worldData.generators.structure.structureContext import StructureContext
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

_SUPPORTED = {"flat", "gable", "hull"}


class RoofBuilder:
    """
    Dispatches roof generation based on context.roof_type.

    flat   — single layer at top_z covering ground-floor footprint
    gable  — shrink on short axis (ridge line)
    hull   — shrink on both axes (hip/pyramid)
    none   — no roof (guard at StructureAssembler level)
    """

    def __init__(
        self,
        world: World,
        building: NamedLocation,
        context: StructureContext,
        ground_z: int,
    ) -> None:
        self.world_uid    = world.world_uid
        self.building_uid = building.location_uid
        self.context      = context
        self.ground_z     = ground_z
        self.mat = (
            context.roof_material
            or building.parent_wall_material
            or "stone"
        )

    def build(self, cells: list[MapCell]) -> list[MapCell]:
        rt = self._resolve_type()
        if rt not in _SUPPORTED:
            return []

        # footprint = ground-floor XY
        footprint = {(c.x, c.y) for c in cells if c.z == self.ground_z}
        if not footprint:
            return []

        # top_z = first z above the highest existing cell
        top_z = max(c.z for c in cells) + 1

        if rt == "flat":
            return self._flat(footprint, top_z)
        if rt == "gable":
            return GableRoof(
                self.world_uid, self.building_uid, self.mat, self.context.slope_step,
            ).build(footprint, top_z)
        if rt == "hull":
            return self._hull(footprint, top_z)
        return []

    def _resolve_type(self) -> str:
        rt = self.context.roof_type
        if isinstance(rt, list):
            for t in rt:
                if t in _SUPPORTED:
                    return t
            return "none"
        return rt

    def _flat(self, footprint: set[tuple[int, int]], top_z: int) -> list[MapCell]:
        wu, bu, mat = self.world_uid, self.building_uid, self.mat
        return [_roof_cell(x, y, top_z, wu, bu, mat) for x, y in footprint]

    def _hull(self, footprint: set[tuple[int, int]], top_z: int) -> list[MapCell]:
        """Hip/pyramid roof: shrink on both axes per z-unit."""
        xs = [x for x, _ in footprint]
        ys = [y for _, y in footprint]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        slope = self.context.slope_step
        half  = min(x_max - x_min + 1, y_max - y_min + 1) / 2
        peak  = math.ceil(half / slope)

        wu, bu, mat = self.world_uid, self.building_uid, self.mat
        result: list[MapCell] = []

        for dz in range(peak + 1):
            shrink = int(dz * slope)
            x_lo = x_min + shrink
            x_hi = x_max - shrink
            y_lo = y_min + shrink
            y_hi = y_max - shrink
            if x_lo > x_hi or y_lo > y_hi:
                break
            for x, y in footprint:
                if x_lo <= x <= x_hi and y_lo <= y <= y_hi:
                    result.append(_roof_cell(x, y, top_z + dz, wu, bu, mat))

        return result
