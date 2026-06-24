import logging

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import ASSEMBLER_REGISTRY
from app.application.worldData.generators.assemblers.structureAssembler.structureContext import StructureContext
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


class StructureAreaAssembler:

    def assemble(
        self,
        world:         World,
        slot:          AreaSlot,
        template:      dict,
        city_skeleton: CitySkeleton,
        terrain_cells: list[MapCell] | None = None,
    ) -> AreaLayout:
        logger.info(
            "StructureAreaAssembler | template=%s facing=%s slot_cells=%d",
            template.get("system_name", "?"),
            slot.facing,
            len(slot.cells),
        )

        building = self._place_building(world, slot, template)
        context  = self._derive_context(template, city_skeleton, slot, terrain_cells)

        structure_type = template.get("structure_type", "building")
        assembler      = ASSEMBLER_REGISTRY.get(structure_type)
        building_layout = assembler.assemble(world, building, template, context, terrain_cells)

        barrier_cells = self._build_barrier(world, slot, template)

        return AreaLayout(
            building_location=building,
            building_layout=building_layout,
            barrier_cells=barrier_cells,
        )

    def _place_building(
        self,
        world:    World,
        slot:     AreaSlot,
        template: dict,
    ) -> NamedLocation:
        """
        Вычисляет позицию здания внутри участка из footprint шаблона и slot.facing.
        Создаёт и возвращает NamedLocation здания с map_x/map_y/map_z.
        """
        raise NotImplementedError

    def _derive_context(
        self,
        template:      dict,
        city_skeleton: CitySkeleton,
        slot:          AreaSlot,
        terrain_cells: list[MapCell] | None,
    ) -> StructureContext:
        """
        Выводит StructureContext из structure_type + architectural_style + terrain.
        Алгоритм не описан в ТЗ — реализовать после появления спецификации.
        """
        raise NotImplementedError

    def _build_barrier(
        self,
        world:    World,
        slot:     AreaSlot,
        template: dict,
    ) -> list[MapCell]:
        """
        Генерирует ячейки забора по периметру slot.cells.
        Probability roll из template["perimeter_barrier"]["probability"].
        Тип забора из template["perimeter_barrier"]["template"] → barrier_template_registry.
        """
        raise NotImplementedError
