from __future__ import annotations

from app.application.worldData.generators.structure.cellFactory import _roof_cell
from app.application.worldData.generators.structure.roof.gableRoof import GableRoof, _shrink_roof_loop
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

        footprint = {(c.x, c.y) for c in cells if c.z == self.ground_z}
        if not footprint:
            return []

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
        slope = self.context.slope_step
        if slope <= 0:
            raise ValueError(f"slope_step must be > 0, got {slope}")
        xs = [x for x, _ in footprint]
        ys = [y for _, y in footprint]
        wu, bu, mat = self.world_uid, self.building_uid, self.mat
        return _shrink_roof_loop(
            footprint, top_z,
            x_min=min(xs), x_max=max(xs),
            y_min=min(ys), y_max=max(ys),
            shrink_x=True, shrink_y=True,
            slope=slope, wu=wu, bu=bu, mat=mat,
        )
