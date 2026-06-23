from dataclasses import dataclass

from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.structureAssembler.baseStructureAssembler import BaseStructureAssembler
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


@dataclass
class VastHullContext:
    hull_type:      str              # "ship" | "spaceship" | "airship" | "submarine"
    orientation:    str = "north"    # направление носа ("north"|"east"|"south"|"west")
    hull_material:  str | None = None        # None → резолвится из шаблона
    deck_count:     int = 1                  # количество палуб/этажей


@ASSEMBLER_REGISTRY.register("vastHull")
class VastHullAssembler(BaseStructureAssembler):
    """
    Генерирует замкнутую корпусную структуру без привязки к terrain и без фундамента.
    Охватывает любой тип крупного подвижного корпуса: корабль, космический корабль, дирижабль.
    Ориентация влияет на расстановку помещений и направление входа.
    """

    def assemble(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
        context: VastHullContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        raise NotImplementedError
