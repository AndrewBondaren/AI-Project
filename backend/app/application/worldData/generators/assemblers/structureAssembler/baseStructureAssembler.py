from abc import ABC, abstractmethod

from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


class BaseStructureAssembler(ABC):

    @abstractmethod
    def assemble(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
        context: object,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout: ...
