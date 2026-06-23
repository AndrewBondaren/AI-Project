from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.structureAssembler.baseStructureAssembler import BaseStructureAssembler
from app.application.worldData.generators.structure.foundation.foundationBuilder import FoundationBuilder
from app.application.worldData.generators.structure.roof.roofBuilder import RoofBuilder
from app.application.worldData.generators.assemblers.structureAssembler.structureContext import StructureContext
from app.application.worldData.generators.structure.structureGeneratorService import (
    StructureGeneratorService,
    StructureLayout,
)
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _build_terrain_surface(terrain_cells: list[MapCell]) -> dict[tuple[int, int], int]:
    surface: dict[tuple[int, int], int] = {}
    for cell in terrain_cells:
        key = (cell.x, cell.y)
        if key not in surface or cell.z > surface[key]:
            surface[key] = cell.z
    return surface


@ASSEMBLER_REGISTRY.register("building")
class BuildingAssembler(BaseStructureAssembler):
    """
    Assembler for above-ground structures: interior + optional foundation + optional roof.

    Cell priority (high → low):
      staircase cells from generator  — never overwritten
      foundation cells                — do not overwrite generator cells
      roof cells                      — always placed on top (no z conflict)
    """

    def assemble(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
        context: StructureContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        ground_z        = context.ground_z if context.ground_z is not None else building.map_z
        terrain_surface = _build_terrain_surface(terrain_cells) if terrain_cells else {}
        fd              = context.foundation_depth if context.foundation_type != "none" else 0

        layout = StructureGeneratorService().generate_from_template(
            world, building, template,
            ground_z=ground_z,
            foundation_depth=fd,
        )

        cells: dict[tuple, MapCell] = {(c.x, c.y, c.z): c for c in layout.cells}

        if context.foundation_type != "none":
            for cell in FoundationBuilder(world, building, context, terrain_surface, ground_z).build(layout.cells):
                key = (cell.x, cell.y, cell.z)
                if key not in cells:
                    cells[key] = cell

        if context.roof_type != "none":
            for cell in RoofBuilder(world, building, context, ground_z).build(layout.cells):
                cells[(cell.x, cell.y, cell.z)] = cell

        layout.cells = list(cells.values())
        return layout
