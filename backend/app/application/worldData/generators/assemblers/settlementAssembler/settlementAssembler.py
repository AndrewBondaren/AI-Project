import logging

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtAssembler import DistrictAssembler
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import plan_district_slots
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    cell_size_m,
    footprint_side_m,
    settlement_origin,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.streets import plan_city_street_grid
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import SettlementLayout
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
            "SettlementAssembler | settlement=%s size=%s density=%s tier=%s",
            settlement.location_uid,
            settlement.system_city_size,
            getattr(settlement, "settlement_density", None),
            settlement.system_economic_tier,
        )

        skeleton       = self._build_skeleton(settlement)
        logger.info(
            "CitySkeleton | economic_tier=%s architectural_style=%s dominant_material=%s"
            " settlement_density=%s city_size=%s mood=%s",
            skeleton.economic_tier,
            skeleton.architectural_style,
            skeleton.dominant_material,
            skeleton.settlement_density,
            skeleton.system_city_size,
            skeleton.system_location_mood,
        )
        district_slots = self._plan_district_slots(world, settlement, skeleton, terrain_cells)

        district_assembler = DistrictAssembler()
        district_layouts: list[DistrictLayout] = []

        for slot in district_slots:
            layout = district_assembler.assemble(world, slot, skeleton, terrain_cells)
            district_layouts.append(layout)

        city_nodes, city_edges = self._plan_street_grid(
            world, settlement, skeleton, district_slots,
        )
        barrier_cells = self._plan_barriers(settlement, skeleton, district_slots)

        logger.info(
            "SettlementAssembler done | settlement=%s districts=%d"
            " city_nodes=%d city_edges=%d barriers=%d",
            settlement.location_uid,
            len(district_layouts),
            len(city_nodes),
            len(city_edges),
            len(barrier_cells),
        )

        return SettlementLayout(
            district_layouts=district_layouts,
            connection_nodes=city_nodes,
            connection_edges=city_edges,
            barrier_cells=barrier_cells,
        )

    def _build_skeleton(self, settlement: NamedLocation) -> CitySkeleton:
        return CitySkeleton(
            economic_tier=        TierResolver.resolve(city=settlement),
            architectural_style=  getattr(settlement, "architectural_style",  None),
            dominant_material=    getattr(settlement, "dominant_material",    None),
            settlement_density=   getattr(settlement, "settlement_density",   None),
            system_city_size=     settlement.system_city_size,
            system_location_mood= settlement.system_location_mood,
        )

    def _plan_district_slots(
        self,
        world:         World,
        settlement:    NamedLocation,
        skeleton:      CitySkeleton,
        terrain_cells: list[MapCell] | None,
    ) -> list[DistrictSlot]:
        return plan_district_slots(world, settlement, skeleton, terrain_cells)

    def _plan_street_grid(
        self,
        world:          World,
        settlement:     NamedLocation,
        skeleton:       CitySkeleton,
        district_slots: list[DistrictSlot],
    ):
        ox, oy, gz = settlement_origin(settlement)
        side_m = footprint_side_m(world, skeleton.system_city_size)
        return plan_city_street_grid(
            ox, oy, gz, side_m, cell_size_m(world),
            district_slots, world.world_uid, skeleton,
        )

    def _plan_barriers(
        self,
        settlement:     NamedLocation,
        skeleton:       CitySkeleton,
        district_slots: list[DistrictSlot],
    ) -> list[MapCell]:
        """v1: стены не генерируются — отложено до barrier_template_registry."""
        _ = (settlement, skeleton, district_slots)
        return []
