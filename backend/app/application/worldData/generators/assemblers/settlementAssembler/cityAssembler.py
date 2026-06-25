import logging

from app.application.worldData.generators.assemblers.cityAssembler.cityLayout import CityLayout
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtAssembler import DistrictAssembler
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


class CityAssembler:

    def assemble(
        self,
        world:         World,
        city:          NamedLocation,
        terrain_cells: list[MapCell] | None = None,
    ) -> CityLayout:
        logger.info(
            "CityAssembler | city=%s size=%s density=%s",
            city.location_uid,
            city.system_city_size,
            getattr(city, "settlement_density", None),
        )

        skeleton           = self._build_skeleton(city)
        district_slots     = self._plan_district_slots(city, skeleton, terrain_cells)
        district_assembler = DistrictAssembler()
        district_layouts: list[DistrictLayout] = []

        for slot in district_slots:
            layout = district_assembler.assemble(world, slot, skeleton, terrain_cells)
            district_layouts.append(layout)

        road_cells    = self._plan_street_grid(city, skeleton)
        barrier_cells = self._plan_city_barriers(city, skeleton)

        return CityLayout(
            district_layouts=district_layouts,
            road_cells=road_cells,
            barrier_cells=barrier_cells,
        )

    def _build_skeleton(self, city: NamedLocation) -> CitySkeleton:
        """
        Единственное место создания CitySkeleton — извлекает поля из NamedLocation поселения.
        Передаётся вниз по иерархии без изменений.
        """
        return CitySkeleton(
            economic_tier=        city.system_economic_tier,
            architectural_style=  getattr(city, "architectural_style",  None),
            dominant_material=    getattr(city, "dominant_material",    None),
            settlement_density=   getattr(city, "settlement_density",   None),
            system_city_size=     city.system_city_size,
            system_location_mood= city.system_location_mood,
        )

    def _plan_district_slots(
        self,
        city:          NamedLocation,
        skeleton:      CitySkeleton,
        terrain_cells: list[MapCell] | None,
    ) -> list[DistrictSlot]:
        """
        Нарезает footprint города на районы.
        Для каждой позиции:
          1. Определяет кандидатов из district_template_registry
          2. Проверяет placement_conditions (adjacent_terrain, min_city_size и др.)
          3. Выбирает шаблон
          4. Вычисляет мировые координаты:
                cell_size_m = world.map_settings["global_cell_size_m"]
                origin_x    = cell_x * cell_size_m + offset
          5. Возвращает DistrictSlot с embedded district_template

        Алгоритм разбивки — открытый вопрос (прямая сетка vs Voronoi).
        """
        raise NotImplementedError

    def _plan_street_grid(
        self,
        city:     NamedLocation,
        skeleton: CitySkeleton,
    ) -> list[MapCell]:
        """
        Генерирует ячейки главных магистралей и улиц.
        Нет ТЗ по механике дорог — зарезервировано.
        """
        raise NotImplementedError

    def _plan_city_barriers(
        self,
        city:     NamedLocation,
        skeleton: CitySkeleton,
    ) -> list[MapCell]:
        """
        Генерирует ячейки городских стен и укреплений.
        Тип и наличие стен зависят от city_size + district_type граничных кварталов.
        """
        raise NotImplementedError
