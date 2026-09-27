from abc import ABC, abstractmethod

from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.dataModel.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.application.worldData.generators.assemblers.buildingAssembler.structureContext import StructureContext
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class BaseBuildingAssembler(ABC):

    @abstractmethod
    def assemble(
        self,
        world: World,
        building: NamedLocation,
        body: BuildingBodyTemplate,
        structure: StructureTemplate,
        context: StructureContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout: ...
