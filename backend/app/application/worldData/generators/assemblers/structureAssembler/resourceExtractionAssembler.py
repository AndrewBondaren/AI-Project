from dataclasses import dataclass

from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.structureAssembler.baseStructureAssembler import BaseStructureAssembler
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass
class ResourceExtractionContext:
    extraction_type:      str              # "mine" | "quarry" | "well"
    depth:                int              # глубина в z-единицах (всегда > 0)
    resource_type:        str | None = None        # добываемый ресурс (iron_ore, coal, …)
    has_surface_building: bool = False             # наземный вход/надстройка над шахтой
    shaft_width:          int = 3                  # ширина шахты в клетках
    ground_z:             int | None = None        # None → resolved from building.map_z


@ASSEMBLER_REGISTRY.register("resourceExtraction")
class ResourceExtractionAssembler(BaseStructureAssembler):
    """
    Генерирует подземную структуру (шахту/карьер/скважину) без крыши.
    При has_surface_building=True дополнительно генерирует наземную надстройку.
    Логика направлена вниз по z (в отличие от BuildingAssembler).
    """

    def assemble(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
        context: ResourceExtractionContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        raise NotImplementedError
