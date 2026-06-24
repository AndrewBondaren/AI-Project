import logging
from dataclasses import dataclass

from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.structureAssembler.baseStructureAssembler import BaseStructureAssembler
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


@dataclass
class RuinsContext:
    base_structure_type: str         # тип до разрушения: "building", "resourceExtraction", …
    decay_level:         float       # 0.0 = лёгкий декай, 1.0 = полное разрушение
    ruin_style:          str = "collapsed"   # "collapsed" | "burned" | "overgrown"
    ground_z:            int | None = None   # None → resolved from building.map_z


@ASSEMBLER_REGISTRY.register("ruins")
class RuinsAssembler(BaseStructureAssembler):
    """
    Генерирует базовую структуру через исходный ассемблер (по base_structure_type),
    затем применяет decay-пасс: удаляет/повреждает ячейки согласно decay_level и ruin_style.
    """

    def assemble(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
        context: RuinsContext,
        terrain_cells: list[MapCell] | None = None,
    ) -> StructureLayout:
        logger.info(
            "RuinsAssembler | template=%s building=%s",
            template.get("system_name", "?"), building.location_uid,
        )
        raise NotImplementedError
