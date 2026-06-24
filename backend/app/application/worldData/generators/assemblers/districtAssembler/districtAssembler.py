import logging

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import StructureAreaAssembler
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)


class DistrictAssembler:

    def assemble(
        self,
        world:         World,
        slot:          DistrictSlot,
        city_skeleton: CitySkeleton,
        terrain_cells: list[MapCell] | None = None,
    ) -> DistrictLayout:
        template = slot.district_template
        logger.info(
            "DistrictAssembler | district_type=%s origin=(%d,%d) size=%dx%d",
            template.get("district_type", "?"),
            slot.origin_x,
            slot.origin_y,
            slot.width_m,
            slot.depth_m,
        )

        area_slots     = self._plan_area_slots(slot)
        area_assembler = StructureAreaAssembler()
        area_layouts: list[AreaLayout] = []

        for area_slot in area_slots:
            building_template = self._assign_template(area_slot, template, city_skeleton)
            layout = area_assembler.assemble(
                world, area_slot, building_template, city_skeleton, terrain_cells
            )
            area_layouts.append(layout)

        street_cells = self._plan_streets(slot)

        return DistrictLayout(
            area_layouts=area_layouts,
            street_cells=street_cells,
        )

    def _plan_area_slots(self, slot: DistrictSlot) -> list[AreaSlot]:
        """
        Нарезает район на участки под здания.
        Размеры участков выводятся из footprint шаблонов зданий
        из slot.district_template + settlement_density.
        """
        raise NotImplementedError

    def _assign_template(
        self,
        area_slot:         AreaSlot,
        district_template: dict,
        city_skeleton:     CitySkeleton,
    ) -> dict:
        """
        Выбирает building_template для участка.
        Фильтр: structure_type совместим с district_type;
                economic_tier совместим с city_skeleton.economic_tier (±1 тир).
        """
        raise NotImplementedError

    def _plan_streets(self, slot: DistrictSlot) -> list[MapCell]:
        """
        Генерирует ячейки внутренних улиц района.
        Нет ТЗ — механика дорог не описана.
        """
        raise NotImplementedError
