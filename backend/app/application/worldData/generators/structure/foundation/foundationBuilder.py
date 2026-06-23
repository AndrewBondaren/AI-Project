from __future__ import annotations

from app.application.worldData.generators.structure.cellBuilder import _wall_cell
from app.application.worldData.generators.structure.cellFactory import _floor_cell
from app.application.worldData.generators.structure.structureContext import StructureContext
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class FoundationBuilder:
    """
    Builds foundation cells below ground_z based on context.foundation_type.

    Priority: staircase cells from generator are NOT overwritten (enforced by StructureAssembler).

    Types (v1):
      slab      — fd-thick slab at full footprint
      perimeter — same but only perimeter cells
      full/hull — fills gap between terrain surface and ground_z per column
    """

    def __init__(
        self,
        world: World,
        building: NamedLocation,
        context: StructureContext,
        terrain_surface: dict[tuple[int, int], int],
        ground_z: int,
    ) -> None:
        self.world_uid      = world.world_uid
        self.building_uid   = building.location_uid
        self.context        = context
        self.terrain_surface = terrain_surface
        self.ground_z       = ground_z
        self.mat = (
            context.foundation_material
            or building.parent_wall_material
            or "stone"
        )

    def build(self, cells: list[MapCell]) -> list[MapCell]:
        footprint = {(c.x, c.y) for c in cells if c.z == self.ground_z}
        ft = self.context.foundation_type
        if ft == "slab":
            return self._slab(footprint)
        if ft == "perimeter":
            return self._slab(_perimeter_only(footprint))
        if ft in ("full", "hull"):
            return self._full(footprint)
        return []

    def _slab(self, footprint: set[tuple[int, int]]) -> list[MapCell]:
        fd   = self.context.foundation_depth
        z_lo = self.ground_z - fd
        wu, bu, mat = self.world_uid, self.building_uid, self.mat
        result: list[MapCell] = []
        for x, y in footprint:
            for z in range(z_lo, self.ground_z):
                if z == z_lo:
                    result.append(_floor_cell(x, y, z, wu, bu, mat))
                else:
                    result.append(_wall_cell(x, y, z, wu, bu, mat))
        return result

    def _full(self, footprint: set[tuple[int, int]]) -> list[MapCell]:
        fd   = self.context.foundation_depth
        wu, bu, mat = self.world_uid, self.building_uid, self.mat
        result: list[MapCell] = []
        for x, y in footprint:
            surface_z = self.terrain_surface.get((x, y), self.ground_z - fd - 1)
            z_lo = min(surface_z + 1, self.ground_z - fd)
            for z in range(z_lo, self.ground_z):
                if z == z_lo:
                    result.append(_floor_cell(x, y, z, wu, bu, mat))
                else:
                    result.append(_wall_cell(x, y, z, wu, bu, mat))
        return result


def _perimeter_only(footprint: set[tuple[int, int]]) -> set[tuple[int, int]]:
    return {
        (x, y) for x, y in footprint
        if not all((x + dx, y + dy) in footprint for dx, dy in _NEIGHBORS)
    }
