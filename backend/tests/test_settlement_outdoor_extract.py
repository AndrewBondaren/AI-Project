"""Outdoor extract / C6 target / C20 front door."""

from __future__ import annotations

import unittest
from dataclasses import replace

from app.application.worldData.settlementOutdoor.settlementOutdoorTransitions import project_settlement_transitions
from app.application.worldData.transitions.transitionStoragePolicy import BuildingTransitionScope
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry

from app.application.worldData.generators.assemblers.areaAssembler.areaLayout import AreaLayout
from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.areaThreshold import (
    AreaThreshold,
    AreaThresholdKind,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtLayout import (
    DistrictLayout,
)
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import (
    DistrictSlot,
)
from app.application.worldData.generators.assemblers.settlementAssembler.settlementLayout import (
    SettlementLayout,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    StructureLayout,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorExtract import (
    ExtractedTopology,
    SettlementOutdoorExtractError,
    extract_settlement,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorSkip import (
    is_settlement_outdoor_target,
)
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    district_location_uid,
)
from app.dataModel.locations.enums.entryRole import EntryRole
from app.dataModel.locations.settlement.district.districtTemplateEntry import DistrictTemplateEntry
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.structure.enums.passageType import PassageType
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.connectionNode import ConnectionNode


def _settlement() -> NamedLocation:
    return NamedLocation(
        location_uid="set-1",
        world_uid="w1",
        display_name="Town",
        system_location_type="settlement",
        created_at="2026-01-01T00:00:00",
        map_x=0,
        map_y=0,
        map_z=0,
        system_city_size="hamlet",
    )


class TestSettlementTransitionProjection(unittest.TestCase):
    def setUp(self):
        self.registry = WorldTransitionTypeRegistry.model_validate([
            *WorldTransitionTypeRegistry.canonical_engine().model_dump(mode="json"),
            {"system_type": "custom_main", "display_name": "Main", "behaves_as": "main_entrance"},
        ])
        self.building = NamedLocation("house", "w1", "House", "building", "2026-10-06",
                                      parent_location_uid="district", entry_difficulty=42, guard_level=20)
        self.locations = {"house": self.building}
        self.levels = {"original-level": LocationLevel("original-level", "house", 0, 3, "Ground")}
        self.main = self.transition("main", "custom_main", source={})
        self.door = self.transition("door", "door", source_side={"entry_difficulty_override": 0})
        self.scope = BuildingTransitionScope("house", frozenset(self.levels), frozenset({"door"}))

    def transition(self, uid, key, **wire):
        endpoint = {"space": "level", "level_uid": "original-level", "x": 1, "y": 2, "z": 0}
        return Transition.model_validate({
            "transition_uid": uid, "world_uid": "w1", "system_transition_type": key,
            "source": endpoint, "destination": {**endpoint, "x": 2},
            "destination_side": {"owner_location_uid": "house"}, **wire,
        }, context={"transition_type_registry": self.registry})

    def project(self, transitions=None, scopes=None, **snapshots):
        return project_settlement_transitions("w1", transitions if transitions is not None else [self.main, self.door],
            building_scopes=scopes if scopes is not None else [self.scope], registry=self.registry,
            levels=snapshots.get("levels", self.levels), locations=snapshots.get("locations", self.locations),
            nodes=snapshots.get("nodes", {}))

    def test_custom_main_sql_and_interior_wire_keep_uids_refs_and_overrides(self):
        result = self.project()
        self.assertEqual(result.sql_transitions, [self.main])
        self.assertIs(result.sql_transitions[0], self.main)
        self.assertIsNone(self.main.source.host_location_uid)
        block = result.pack_by_building["house"]
        self.assertEqual(block.level_uids, ["original-level"])
        self.assertEqual(block.transitions, [self.door])
        self.assertEqual(block.transitions[0].source_side.entry_difficulty_override, 0)
        self.assertIsNone(block.transitions[0].destination_side.entry_difficulty_override)
        self.assertEqual(self.building.entry_difficulty, 42)
        self.assertEqual(self.building.guard_level, 20)
        self.assertEqual(self.building.parent_location_uid, "district")
        self.assertEqual(self.levels["original-level"].location_uid, "house")

    def test_service_hidden_and_source_owner_cannot_replace_main(self):
        for key in ("service_entrance", "hidden_entrance", "door"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "MAIN_ENTRANCE"):
                self.project([self.transition("entry", key, source={})], scopes=[replace(self.scope, transition_uids=frozenset())])
        source_owned = self.transition("wrong", "main_entrance", source={},
            source_side={"owner_location_uid": "house"}, destination_side={})
        with self.assertRaisesRegex(ValueError, "MAIN_ENTRANCE"):
            self.project([source_owned, self.door])

    def test_multiple_main_service_and_hidden_entries_preserve_state(self):
        service = self.transition("service", "service_entrance", source={})
        hidden = self.transition("hidden", "hidden_entrance", source={})
        second_main = self.transition("main2", "main_entrance", source={}, is_active=False,
            destination_side={"owner_location_uid": "house", "is_accessible": False})
        result = self.project([self.main, service, hidden, second_main, self.door])
        self.assertEqual(result.sql_transitions, [self.main, service, hidden, second_main])
        self.assertFalse(result.sql_transitions[2].destination_side.is_discovered)
        self.assertFalse(result.sql_transitions[3].is_active)

    def test_no_parent_or_area_location_required_and_empty_interior_is_explicit(self):
        unparented = replace(self.building, parent_location_uid=None)
        result = self.project([self.main], scopes=[replace(self.scope, transition_uids=frozenset())],
                              locations={"house": unparented})
        self.assertEqual(result.pack_by_building["house"].transitions, [])
        self.assertIsNone(unparented.parent_location_uid)
        self.assertEqual(set(self.locations), {"house"})

    def test_runtime_and_undeclared_interior_stay_sql(self):
        runtime = self.transition("runtime", "door", origin="runtime")
        undeclared = self.transition("undeclared", "door")
        scopes = [replace(self.scope, transition_uids=frozenset({"door", "runtime"}))]
        result = self.project([self.main, self.door, runtime, undeclared], scopes=scopes)
        self.assertEqual(result.sql_transitions, [self.main, runtime, undeclared])
        self.assertEqual(result.pack_by_building["house"].transitions, [self.door])

    def test_reference_validation_precedes_projection(self):
        for patched in (
            self.main.model_copy(update={"world_uid": "other"}),
            self.transition("bad", "main_entrance", source={"node_uid": "missing", "x": 0, "y": 0, "z": 0}),
            self.transition("bad", "main_entrance", source={}, destination_side={"owner_location_uid": "missing"}),
        ):
            with self.subTest(patched=patched.transition_uid), self.assertRaises(ValueError):
                self.project([patched, self.door])
        with self.assertRaises(ValueError):
            self.project(levels={})

    def test_node_refs_are_validated_and_retained(self):
        entry = self.transition("node-entry", "main_entrance", source={
            "node_uid": "node", "x": 5, "y": 6, "z": 0})
        node = ConnectionNode("node", 5, 6, 0, "building_entrance", "area", "w1")
        result = self.project([entry, self.door], nodes={"node": node})
        self.assertEqual(result.sql_transitions[0].source.node_uid, "node")
        with self.assertRaises(ValueError):
            self.project([entry, self.door], nodes={"node": replace(node, x=99)})

    def test_topology_new_fields_are_empty_and_independent_until_cutover(self):
        first = ExtractedTopology([], [], [])
        second = ExtractedTopology([], [], [])
        first.sql_transitions.append(self.main)
        first.pack_by_building.update(self.project().pack_by_building)
        self.assertEqual(second.sql_transitions, [])
        self.assertEqual(second.pack_by_building, {})

    def test_projection_without_building_layout_scopes_is_sql_only(self):
        result = self.project(scopes=[])
        self.assertEqual(result.sql_transitions, [self.main, self.door])
        self.assertEqual(result.pack_by_building, {})

    def test_duplicate_missing_scope_refs_and_wrong_world_rejected(self):
        for scopes in (
            [self.scope, self.scope],
            [replace(self.scope, building_uid="missing")],
            [replace(self.scope, level_uids=frozenset({"missing"}))],
            [replace(self.scope, transition_uids=frozenset({"missing"}))],
        ):
            with self.subTest(scopes=scopes), self.assertRaises(ValueError):
                self.project(scopes=scopes)
        with self.assertRaisesRegex(ValueError, "duplicate transition UID"):
            self.project([self.main, self.door, self.door])
        with self.assertRaises(ValueError):
            self.project(locations={"house": replace(self.building, world_uid="other")})


def _layout(
    *,
    passages: list[LocationPassage],
    cells: list[MapCell] | None = None,
) -> SettlementLayout:
    template = DistrictTemplateEntry(
        system_name="core",
        display_name="Core",
        district_type="civic",
    )
    dslot = DistrictSlot(
        origin_x=0,
        origin_y=0,
        width_fine=10,
        depth_fine=10,
        ground_z=0,
        district_template=template,
    )
    aslot = AreaSlot(cells=[(0, 0), (1, 0)], ground_z=0, facing=Facing.SOUTH)
    threshold = AreaThreshold(
        kind=AreaThresholdKind.DOOR, cells=[(0, 0)], z=0,
    )
    probe = NamedLocation(
        location_uid="probe-hut-0-0",
        world_uid="w1",
        display_name="Hut",
        system_location_type="building",
        created_at="2026-01-01T00:00:00",
        map_x=0,
        map_y=0,
        map_z=0,
        system_template_uid="hut",
    )
    level = LocationLevel(
        level_uid="old-level",
        location_uid="probe-hut-0-0",
        z=0,
        z_height=3,
        display_name="ground",
    )
    building_layout = StructureLayout(
        cells=list(cells or []),
        levels=[level],
        passages=passages,
        rooms=[],
    )
    area = AreaLayout(
        slot=aslot,
        threshold=threshold,
        building_location=probe,
        building_layout=building_layout,
    )
    district = DistrictLayout(slot=dslot, area_layouts=[area])
    return SettlementLayout(district_layouts=[district])


class TestSettlementOutdoorExtract(unittest.TestCase):

    def test_c6_settlement_yes_district_no(self):
        self.assertTrue(is_settlement_outdoor_target(_settlement()))
        district = NamedLocation(
            location_uid="d1",
            world_uid="w1",
            display_name="Core",
            system_location_type="district",
            created_at="2026-01-01T00:00:00",
        )
        self.assertFalse(is_settlement_outdoor_target(district))

    def test_c20_missing_front_raises(self):
        with self.assertRaises(SettlementOutdoorExtractError):
            extract_settlement(_settlement(), _layout(passages=[]))

    def test_front_entry_and_district_parent(self):
        passage = LocationPassage(
            passage_uid="p-front",
            world_uid="w1",
            to_level_uid="old-level",
            to_x=1,
            to_y=0,
            system_passage_type=PassageType.MAIN_ENTRANCE,
            from_level_uid=None,
        )
        extracted = extract_settlement(_settlement(), _layout(passages=[passage]))
        self.assertEqual(len(extracted.districts), 1)
        self.assertIsNone(extracted.districts[0].system_template_uid)
        self.assertEqual(
            extracted.districts[0].district_topology["template_system_name"],
            "core",
        )
        self.assertEqual(len(extracted.buildings), 1)
        self.assertEqual(extracted.buildings[0].system_template_uid, "hut")
        self.assertEqual(
            extracted.buildings[0].parent_location_uid,
            extracted.districts[0].location_uid,
        )
        self.assertEqual(len(extracted.entry_points), 1)
        self.assertEqual(extracted.entry_points[0].entry_role, EntryRole.FRONT.value)
        self.assertTrue(extracted.entry_points[0].is_discovered)
        self.assertEqual(extracted.wire.settlement_uid, "set-1")
        self.assertEqual(len(extracted.wire.districts), 1)
        self.assertEqual(extracted.sql_transitions, [])
        self.assertEqual(extracted.pack_by_building, {})
        self.assertIsNone(extracted.wire.districts[0].areas[0].buildings[0].interior_transitions)

    def test_building_cells_persist_floor_and_stair(self):
        passage = LocationPassage(
            passage_uid="p-front",
            world_uid="w1",
            to_level_uid="old-level",
            to_x=1,
            to_y=0,
            system_passage_type=PassageType.MAIN_ENTRANCE,
            from_level_uid=None,
        )
        cells = [
            MapCell(
                world_uid="w1", x=0, y=0, z=0,
                system_building_element="wall",
            ),
            MapCell(
                world_uid="w1", x=1, y=0, z=0,
                system_building_element="floor",
            ),
            MapCell(
                world_uid="w1", x=1, y=0, z=1,
                system_building_element="staircase",
                system_facing="north",
            ),
        ]
        extracted = extract_settlement(
            _settlement(),
            _layout(passages=[passage], cells=cells),
        )
        shell = extracted.wire.districts[0].areas[0].buildings[0].shell_cells
        elements = {c.system_building_element for c in shell}
        self.assertEqual(elements, {"wall", "floor", "staircase"})
        stair = next(c for c in shell if c.system_building_element == "staircase")
        self.assertEqual(stair.system_facing, "north")
        self.assertEqual(len(extracted.entry_points), 1)

    def test_plot_without_building_skips_c20(self):
        template = DistrictTemplateEntry(
            system_name="core",
            display_name="Core",
            district_type="civic",
        )
        dslot = DistrictSlot(
            origin_x=0, origin_y=0, width_fine=10, depth_fine=10, ground_z=0,
            district_template=template,
        )
        aslot = AreaSlot(cells=[(0, 0), (1, 0), (0, 1), (1, 1)], ground_z=2, facing=Facing.SOUTH)
        threshold = AreaThreshold(
            kind=AreaThresholdKind.PARCEL_EDGE, cells=[(0, 0)], z=2,
        )
        area = AreaLayout(slot=aslot, threshold=threshold)
        district = DistrictLayout(slot=dslot, area_layouts=[area])
        extracted = extract_settlement(_settlement(), SettlementLayout(district_layouts=[district]))
        self.assertEqual(len(extracted.buildings), 0)
        self.assertEqual(len(extracted.entry_points), 0)
        self.assertEqual(len(extracted.wire.districts[0].areas), 1)
        self.assertEqual(extracted.wire.districts[0].areas[0].buildings, [])
        self.assertEqual(extracted.wire.districts[0].areas[0].slot.ground_z, 2)

    def test_extract_uses_slot_index_not_enumerate(self):
        template = DistrictTemplateEntry(
            system_name="core",
            display_name="Core",
            district_type="civic",
        )
        dslot = DistrictSlot(
            origin_x=0, origin_y=0, width_fine=10, depth_fine=10, ground_z=0,
            district_template=template,
            slot_index=2,
        )
        aslot = AreaSlot(cells=[(0, 0)], ground_z=0, facing=Facing.SOUTH)
        area = AreaLayout(
            slot=aslot,
            threshold=AreaThreshold(
                kind=AreaThresholdKind.PARCEL_EDGE, cells=[(0, 0)], z=0,
            ),
        )
        extracted = extract_settlement(
            _settlement(),
            SettlementLayout(district_layouts=[DistrictLayout(slot=dslot, area_layouts=[area])]),
        )
        expected = district_location_uid("w1", "set-1", "core", 2)
        self.assertEqual(extracted.districts[0].location_uid, expected)
        self.assertEqual(extracted.wire.districts[0].location_uid, expected)
        self.assertNotEqual(
            expected, district_location_uid("w1", "set-1", "core", 0),
        )


if __name__ == "__main__":
    unittest.main()
