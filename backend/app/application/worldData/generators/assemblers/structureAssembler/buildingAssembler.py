import logging

from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.structureAssembler.baseStructureAssembler import BaseStructureAssembler
from app.application.worldData.generators.coordinates.columnSurface import column_surface
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

logger = logging.getLogger(__name__)


@ASSEMBLER_REGISTRY.register("building")
class BuildingAssembler(BaseStructureAssembler):
    """
    Assembler for above-ground structures: interior + optional foundation + optional roof.

    Cell priority (high → low):
      staircase cells from generator  — never overwritten
      foundation cells                — do not overwrite generator cells
      roof cells                      — always placed on top (no z conflict)
    """

    @staticmethod
    def attach_envelope(
        world: World,
        building: NamedLocation,
        layout: StructureLayout,
        context: StructureContext,
        terrain_cells: list[MapCell] | None,
    ) -> StructureLayout:
        """Foundation + roof on a standing interior layout. Does not regenerate rooms."""
        ground_z = context.ground_z if context.ground_z is not None else building.map_z
        terrain_surface = column_surface(terrain_cells)
        cells: dict[tuple, MapCell] = {(c.x, c.y, c.z): c for c in layout.cells}

        if context.foundation_type != "none":
            for cell in FoundationBuilder(
                world, building, context, terrain_surface, ground_z,
            ).build(layout.cells):
                key = (cell.x, cell.y, cell.z)
                if key not in cells:
                    cells[key] = cell

        if context.roof_type != "none":
            for cell in RoofBuilder(world, building, context, ground_z).build(layout.cells):
                cells[(cell.x, cell.y, cell.z)] = cell

        layout.cells = list(cells.values())
        return layout

    def assemble(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
        context: StructureContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        logger.info(
            "BuildingAssembler | template=%s building=%s",
            template.get("system_name", "?"), building.location_uid,
        )
        ground_z = context.ground_z if context.ground_z is not None else building.map_z
        fd = context.foundation_depth if context.foundation_type != "none" else 0

        layout = StructureGeneratorService().generate_from_template(
            world, building, template,
            ground_z=ground_z,
            foundation_depth=fd,
        )
        return self.attach_envelope(world, building, layout, context, terrain_cells)
