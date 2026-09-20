"""
SettlementAssembler — оркестратор генерации поселения.

План реализации по фазам: `.cursor/plans/settlement-assembler.md`

Текущий статус (v1):
  ✅ Фаза A — CitySkeleton, district slots, entry_nodes, city/district connection graph
  ✅ Фаза B — semantic-first city edges (material, has_sidewalk, sidewalk_width log)
  ✅ Фаза C — placement (specialization, economic compat, ground_z, required_structures)
  ✅ Фаза E — building cache, area slots, cached layout in StructureAreaAssembler
  ✅ Фаза D — perimeter barriers (barrier_template_registry)
  ✅ Фаза F — map occupancy, layoutCells, SettlementGeneratorService, lazy_settlement node
  ⬜ Фаза G–H — organic footprint, z-topology

ТЗ: docs/tz_assembler_hierarchy.md, tz_city_generation.md, tz_structure_connections.md §5
"""
import logging
import random
import time
from dataclasses import replace

from app.application.worldData.generators.assemblers.citySkeleton import (
    CitySkeleton,
    city_skeleton_from_settlement,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtAssembler import DistrictAssembler
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import DistrictLayout
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.buildingCache import build_layout_cache
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.mapOccupancy import (
    plan_footprint_occupancy_cells,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.barriers import (
    plan_settlement_barriers,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.dominantMaterial import (
    resolve_dominant_material,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.topologyPlan import (
    plan_city_graph_for_slots,
    plan_slots_and_city_graph,
)
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import SettlementLayout
from app.application.worldData.generators.assemblers.settlementAssembler.timings import (
    SettlementAssembleTimings,
)
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
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
        catalog:       BuildingCatalog | None = None,
        *,
        district_slots: list[DistrictSlot] | None = None,
        city_graph: tuple[list[ConnectionNode], list[ConnectionEdge]] | None = None,
        timings: SettlementAssembleTimings | None = None,
    ) -> SettlementLayout:
        wall0 = time.perf_counter()
        skeleton = self._build_skeleton(world, settlement)
        catalog = catalog or assemble_building_catalog(world)
        logger.info(
            "SettlementAssembler | settlement=%s size=%s density=%s tier=%s",
            settlement.location_uid,
            settlement.system_city_size,
            settlement.settlement_density,
            skeleton.economic_tier,
        )
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
        if district_slots is None:
            planned_slots, planned_nodes, planned_edges = plan_slots_and_city_graph(
                world, settlement, skeleton, terrain_cells,
            )
            district_slots = planned_slots
            if city_graph is None:
                city_graph = (planned_nodes, planned_edges)

        t = time.perf_counter()
        layout_cache = build_layout_cache(
            world, skeleton, district_slots, terrain_cells, catalog=catalog,
            settlement_uid=settlement.location_uid,
        )
        if timings is not None:
            timings.cache_s += time.perf_counter() - t
        logger.info(
            "SettlementAssembler | building_cache templates=%d names=%s",
            len(layout_cache),
            layout_cache.keys(),
        )

        district_assembler = DistrictAssembler()
        district_layouts: list[DistrictLayout] = []

        for slot in district_slots:
            layout = district_assembler.assemble(
                world, slot, skeleton, terrain_cells, layout_cache=layout_cache,
                settlement_uid=settlement.location_uid,
                catalog=catalog,
                timings=timings,
            )
            district_layouts.append(layout)

        t = time.perf_counter()
        if city_graph is None:
            city_nodes, city_edges = plan_city_graph_for_slots(
                world, settlement, skeleton, district_slots, terrain_cells,
            )
        else:
            city_nodes, city_edges = city_graph
        if timings is not None:
            timings.streets_s += time.perf_counter() - t
        t = time.perf_counter()
        barrier_cells = self._plan_barriers(world, settlement, skeleton)
        if timings is not None:
            timings.barriers_s += time.perf_counter() - t
        t = time.perf_counter()
        occupancy_cells = plan_footprint_occupancy_cells(world, settlement, skeleton.system_city_size)
        if timings is not None:
            timings.occupancy_s += time.perf_counter() - t

        layout = SettlementLayout(
            district_layouts=district_layouts,
            connection_nodes=city_nodes,
            connection_edges=city_edges,
            occupancy_cells=occupancy_cells,
            barrier_cells=barrier_cells,
        )
        dominant_material = resolve_dominant_material(
            world, layout, skeleton, settlement_uid=settlement.location_uid,
        )

        logger.info(
            "SettlementAssembler done | settlement=%s districts=%d"
            " city_nodes=%d city_edges=%d barriers=%d occupancy=%d dominant_material=%r",
            settlement.location_uid,
            len(district_layouts),
            len(city_nodes),
            len(city_edges),
            len(barrier_cells),
            len(occupancy_cells),
            dominant_material,
        )
        if timings is not None:
            timings.generate_s = time.perf_counter() - wall0

        return replace(layout, dominant_material=dominant_material)

    def _build_skeleton(self, world: World, settlement: NamedLocation) -> CitySkeleton:
        return city_skeleton_from_settlement(
            settlement,
            economic_tier=TierResolver.resolve(world=world, city=settlement),
        )

    def _plan_barriers(
        self,
        world:      World,
        settlement: NamedLocation,
        skeleton:   CitySkeleton,
    ) -> list[MapCell]:
        rng = random.Random(f"{world.world_uid}_{settlement.location_uid}_barriers")
        return plan_settlement_barriers(world, settlement, skeleton, rng)
