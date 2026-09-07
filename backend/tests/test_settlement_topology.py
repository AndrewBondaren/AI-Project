"""C23 settlement topology — freeze slots, skip, deterministic city uids."""

from __future__ import annotations

import random
import unittest

from app.application.worldData.generators.assemblers.citySkeleton import (
    city_skeleton_from_settlement,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.districts import (
    plan_district_slots,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_side_fine,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.streets import (
    plan_city_street_grid,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementGeneratorService import (
    SettlementGeneratorService,
)
from app.application.worldData.generators.coordinates import map_cell_fine_span, settlement_origin_fine
from app.application.worldData.generators.utils.tierResolver import TierResolver
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    extract_topology,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTopology import (
    has_authored_non_district_children,
    load_topology_slots,
    should_skip_topology,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorTypes import (
    district_type_entry,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    district_location_uid,
)
from app.dataModel.connections.enums.connectionNodeType import ConnectionNodeType
from app.dataModel.connections.enums.graphLevel import GraphLevel
from app.dataModel.locations.locationType.worldLocationTypeRegistry import (
    WorldLocationTypeRegistry,
)
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.settlement.district.districtTopologySlot import DistrictTopologySlot
from app.dataModel.settlement.enums.districtDensity import DistrictDensity
from app.db.models.connectionNode import ConnectionNode
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World


def _world(**kwargs) -> World:
    payload = {
        "world_uid": "w-topo",
        "name": "Test",
        "created_at": "2026-01-01T00:00:00",
        "fine_cells_per_map_cell": 16,
        "city_size_registry": [
            {"system_size": "town", "display_size": "Town", "footprint_multiplier": 1.0},
        ],
    }
    payload.update(kwargs)
    return World(**payload)


def _settlement() -> NamedLocation:
    return NamedLocation(
        location_uid="loc-hold",
        world_uid="w-topo",
        display_name="Hold",
        system_location_type=WorldLocationTypeRegistry.SYSTEM_TYPE_SETTLEMENT,
        created_at="2026-01-01T00:00:00",
        system_location_subtype="city",
        system_city_size="town",
        system_economic_tier="standard",
        settlement_density=DistrictDensity.MEDIUM.wire_value,
        architectural_style="gothic",
        perimeter_barrier=PerimeterBarrier(
            template="stone_fence", probability=1.0,
        ).model_dump(mode="json"),
        map_x=0,
        map_y=0,
        map_z=0,
    )


def _skeleton(world: World, settlement: NamedLocation):
    return city_skeleton_from_settlement(
        settlement,
        economic_tier=TierResolver.resolve(world=world, city=settlement),
    )


def _plan_city(world: World, settlement: NamedLocation, slots):
    skeleton = _skeleton(world, settlement)
    origin = settlement_origin_fine(settlement)
    rng = random.Random(f"{world.world_uid}_{settlement.location_uid}")
    return plan_city_street_grid(
        origin.x, origin.y, origin.z,
        footprint_side_fine(world, skeleton.system_city_size),
        map_cell_fine_span(world),
        slots, world.world_uid, world, rng, skeleton,
        settlement_uid=settlement.location_uid,
    )


class CitySkeletonImportTest(unittest.TestCase):
    def test_density_and_barrier_from_named_location_fields(self) -> None:
        world = _world()
        settlement = _settlement()
        skeleton = _skeleton(world, settlement)
        self.assertEqual(skeleton.settlement_density, DistrictDensity.MEDIUM.wire_value)
        self.assertEqual(skeleton.architectural_style, "gothic")
        self.assertIsNotNone(skeleton.perimeter_barrier)
        self.assertEqual(skeleton.perimeter_barrier.template, "stone_fence")
        self.assertIsNone(skeleton.dominant_material)


class TopologyExtractTest(unittest.TestCase):
    def test_extract_topology_has_districts_and_gates_no_buildings(self) -> None:
        world = _world()
        settlement = _settlement()
        slots = plan_district_slots(world, settlement, _skeleton(world, settlement), None)
        self.assertTrue(slots)
        nodes, edges = _plan_city(world, settlement, slots)
        extracted = extract_topology(settlement, slots, nodes, edges)
        self.assertEqual(len(extracted.districts), len(slots))
        district_type = district_type_entry().system_type
        self.assertTrue(
            all(row.system_location_type == district_type for row in extracted.districts),
        )
        self.assertTrue(all(row.district_topology for row in extracted.districts))
        expected_uid = district_location_uid(
            settlement.location_uid,
            slots[0].district_template.system_name,
            0,
        )
        self.assertEqual(extracted.districts[0].location_uid, expected_uid)
        gates = [
            node for node in extracted.nodes
            if node.node_type == ConnectionNodeType.SETTLEMENT_GATE.value
            and node.graph_level == GraphLevel.CITY.value
        ]
        self.assertTrue(gates)
        self.assertTrue(extracted.edges)
        self.assertTrue(
            all(edge.graph_level == GraphLevel.CITY.value for edge in extracted.edges),
        )
        self.assertFalse(hasattr(extracted, "buildings"))
        self.assertFalse(hasattr(extracted, "wire"))

    def test_city_node_uids_are_stable(self) -> None:
        world = _world()
        settlement = _settlement()
        slots = plan_district_slots(world, settlement, _skeleton(world, settlement), None)
        first_nodes, first_edges = _plan_city(world, settlement, slots)
        second_nodes, second_edges = _plan_city(world, settlement, slots)
        self.assertEqual(
            [node.node_uid for node in first_nodes],
            [node.node_uid for node in second_nodes],
        )
        self.assertEqual(
            [edge.edge_uid for edge in first_edges],
            [edge.edge_uid for edge in second_edges],
        )


class TopologyReuseTest(unittest.TestCase):
    def test_load_slots_keeps_types_and_uids(self) -> None:
        world = _world()
        settlement = _settlement()
        skeleton = _skeleton(world, settlement)
        slots = plan_district_slots(world, settlement, skeleton, None)
        nodes, edges = _plan_city(world, settlement, slots)
        extracted = extract_topology(settlement, slots, nodes, edges)
        loaded = load_topology_slots(
            world, settlement, skeleton, extracted.districts,
        )
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded), len(slots))
        planned_keys = [
            (slot.cell_x, slot.cell_y, slot.district_template.system_name)
            for slot in slots
        ]
        loaded_keys = [
            (slot.cell_x, slot.cell_y, slot.district_template.system_name)
            for slot in loaded
        ]
        self.assertEqual(planned_keys, loaded_keys)
        service = SettlementGeneratorService()
        packed = service.generate_layout(
            world, settlement, catalog=None,
            district_slots=loaded,
            city_graph=(nodes, edges),
        )
        packed_keys = [
            (layout.slot.cell_x, layout.slot.cell_y, layout.slot.district_template.system_name)
            for layout in packed.district_layouts
        ]
        self.assertEqual(planned_keys, packed_keys)
        self.assertEqual(
            [node.node_uid for node in packed.connection_nodes],
            [node.node_uid for node in nodes],
        )


class TopologySkipTest(unittest.TestCase):
    def test_authored_non_district_children_skip(self) -> None:
        building_type = WorldLocationTypeRegistry.canonical_engine().entry_for(
            WorldLocationTypeRegistry.SYSTEM_TYPE_BUILDING,
        )
        assert building_type is not None
        tavern = NamedLocation(
            location_uid="tavern-1",
            world_uid="w-topo",
            display_name="Inn",
            system_location_type=building_type.system_type,
            created_at="2026-01-01T00:00:00",
        )
        self.assertTrue(has_authored_non_district_children([tavern]))
        self.assertTrue(should_skip_topology([tavern], []))

    def test_topology_districts_and_gates_skip(self) -> None:
        district_type = district_type_entry().system_type
        freeze = DistrictTopologySlot(
            cell_x=0,
            cell_y=0,
            origin_x=0,
            origin_y=0,
            width_fine=16,
            depth_fine=16,
            ground_z=0,
            template_system_name="core",
            slot_index=0,
        )
        district = NamedLocation(
            location_uid="d-1",
            world_uid="w-topo",
            display_name="Core",
            system_location_type=district_type,
            created_at="2026-01-01T00:00:00",
            district_topology=freeze.model_dump(mode="json"),
        )
        incomplete = NamedLocation(
            location_uid="d-bad",
            world_uid="w-topo",
            display_name="Core",
            system_location_type=district_type,
            created_at="2026-01-01T00:00:00",
            district_topology={"cell_x": 0},
        )
        gate = ConnectionNode(
            node_uid="g1",
            x=0, y=0, z=0,
            node_type=ConnectionNodeType.SETTLEMENT_GATE.value,
            graph_level=GraphLevel.CITY.value,
            world_uid="w-topo",
            location_uid="loc-hold",
        )
        self.assertTrue(should_skip_topology([district], [gate]))
        self.assertFalse(should_skip_topology([district], []))
        self.assertFalse(should_skip_topology([incomplete], [gate]))


if __name__ == "__main__":
    unittest.main()
