import logging
from dataclasses import dataclass

from app.application.worldData.generators.assemblers.buildingAssembler.assemblerRegistry import BUILDING_ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.buildingAssembler.baseBuildingAssembler import BaseBuildingAssembler
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.dataModel.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.application.worldData.generators.assemblers.buildingAssembler.structureContext import StructureContext
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World
from app.dataModel.spatial.facing import Facing

logger = logging.getLogger(__name__)


@dataclass
class VastHullContext:
    hull_type:      str              # "ship" | "spaceship" | "airship" | "submarine"
    orientation:    str = Facing.NORTH.value    # направление носа (cardinal wire)
    hull_material:  str | None = None        # None → резолвится из шаблона
    deck_count:     int = 1                  # количество палуб/этажей


@BUILDING_ASSEMBLER_REGISTRY.register("vastHull")
class VastHullAssembler(BaseBuildingAssembler):
    """
    Генерирует замкнутую корпусную структуру без привязки к terrain и без фундамента.
    Охватывает любой тип крупного подвижного корпуса: корабль, космический корабль, дирижабль.
    Ориентация влияет на расстановку помещений и направление входа.
    """

    def assemble(
        self,
        world: World,
        building: NamedLocation,
        body: BuildingBodyTemplate,
        structure: StructureTemplate,
        context: StructureContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        logger.info(
            "VastHullAssembler | template=%s building=%s",
            structure.system_name, building.location_uid,
        )
        raise NotImplementedError
