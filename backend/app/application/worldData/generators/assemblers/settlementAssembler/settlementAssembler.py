import logging

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtAssembler import DistrictAssembler
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import SettlementLayout
from app.db.models.connectionEdge import ConnectionEdge
from app.db.models.connectionNode import ConnectionNode
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)


class SettlementAssembler:

    def assemble(
        self,
        world:         World,
        settlement:    NamedLocation,
        terrain_cells: list[MapCell] | None = None,
    ) -> SettlementLayout:
        logger.info(
            "SettlementAssembler | settlement=%s size=%s density=%s",
            settlement.location_uid,
            settlement.system_city_size,
            getattr(settlement, "settlement_density", None),
        )

        skeleton           = self._build_skeleton(settlement)
        district_slots     = self._plan_district_slots(settlement, skeleton, terrain_cells)
        district_assembler = DistrictAssembler()
        district_layouts: list[DistrictLayout] = []

        for slot in district_slots:
            layout = district_assembler.assemble(world, slot, skeleton, terrain_cells)
            district_layouts.append(layout)

        city_nodes, city_edges = self._plan_street_grid(settlement, skeleton)
        barrier_cells          = self._plan_barriers(settlement, skeleton)

        return SettlementLayout(
            district_layouts = district_layouts,
            connection_nodes = city_nodes,
            connection_edges = city_edges,
            barrier_cells    = barrier_cells,
        )

    def _build_skeleton(self, settlement: NamedLocation) -> CitySkeleton:
        """
        Единственное место создания CitySkeleton — извлекает поля из NamedLocation поселения.
        Передаётся вниз по иерархии без изменений.
        """
        return CitySkeleton(
            economic_tier=        settlement.system_economic_tier,
            architectural_style=  getattr(settlement, "architectural_style",  None),
            dominant_material=    getattr(settlement, "dominant_material",    None),
            settlement_density=   getattr(settlement, "settlement_density",   None),
            system_city_size=     settlement.system_city_size,
            system_location_mood= settlement.system_location_mood,
        )

    def _plan_district_slots(
        self,
        settlement:    NamedLocation,
        skeleton:      CitySkeleton,
        terrain_cells: list[MapCell] | None,
    ) -> list[DistrictSlot]:
        """
        Нарезает footprint поселения на районы.
        Footprint = city_size_registry[settlement.system_city_size].footprint_multiplier
                    × world.map_cell_size_m.
        Для каждого района:
          1. Выбирает district_template из district_template_registry
          2. Проверяет placement_conditions
          3. Создаёт entry_nodes на гранях района (через _plan_entry_nodes)
          4. Возвращает DistrictSlot с entry_nodes

        Алгоритм разбивки v1 — равномерная прямоугольная сетка районов.
        """
        raise NotImplementedError

    def _plan_street_grid(
        self,
        settlement: NamedLocation,
        skeleton:   CitySkeleton,
    ) -> tuple[list[ConnectionNode], list[ConnectionEdge]]:
        """
        Генерирует settlement_gate-узлы на границах map_cell
        и межрайонные intersection-узлы на стыках районов.
        Передаёт entry_nodes в DistrictSlot до генерации районов.
        """
        raise NotImplementedError

    def _plan_barriers(
        self,
        settlement: NamedLocation,
        skeleton:   CitySkeleton,
    ) -> list[MapCell]:
        """
        Генерирует ячейки городских стен и укреплений.
        Тип и наличие стен зависят от city_size + district_type граничных районов.
        """
        raise NotImplementedError
