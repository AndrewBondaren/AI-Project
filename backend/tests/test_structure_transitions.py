"""Final geometry identity, shared aggregate validation and outward legacy projection."""

import unittest
from dataclasses import replace

from app.application.worldData.generators.structure.layoutTranslate import translate_layout
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService, StructureLayout
from app.application.worldData.generators.structure.physicalTransition import physical_transition, level_endpoint
from app.application.worldData.generators.assemblers.settlementAssembler.layoutCells import rebind_layout_to_building
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.application.worldData.transitions.transitionValidation import validate_transitions
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.models.locationLevel import LocationLevel
from tests.test_structure_orientation import simple_structure, test_world_building


class StructureTransitionsTest(unittest.TestCase):
    def setUp(self):
        self.world, self.building = test_world_building()
        self.layout = StructureGeneratorService().generate_from_template(self.world, self.building, simple_structure())

    def assert_identity(self, items):
        for item in items:
            self.assertEqual(item.transition_uid, transition_uid(
                item.world_uid, item.system_transition_type, item.source, item.destination))

    def test_generated_entry_uses_surface_real_geometry_bidirectionality_and_owner(self):
        self.assert_identity(self.layout.transitions)
        entry = next(item for item in self.layout.transitions if item.system_transition_type == "main_entrance")
        self.assertTrue(entry.is_bidirectional)
        self.assertEqual(entry.source.space, "surface")
        self.assertIsNone(entry.source.host_location_uid)
        self.assertIsNone(entry.source_side.owner_location_uid)
        self.assertIsNotNone(entry.source.geometry)
        self.assertEqual(entry.destination_side.owner_location_uid, self.building.location_uid)
        validate_transitions(self.world.world_uid, self.layout.transitions,
            levels={level.level_uid: level for level in self.layout.levels},
            locations={self.building.location_uid: self.building}, nodes={},
            registry=WorldTransitionTypeRegistry.canonical_engine())

    def test_translation_moves_both_endpoints_in_xyz_and_reverses_without_identity_drift(self):
        moved = translate_layout(self.layout, 101, -23, 11)
        self.assert_identity(moved.transitions)
        for old, new in zip(self.layout.transitions, moved.transitions, strict=True):
            self.assertNotEqual(old.transition_uid, new.transition_uid)
            for before, after in ((old.source, new.source), (old.destination, new.destination)):
                self.assertEqual(after.geometry, (before.x + 101, before.y - 23, before.z + 11))
                self.assertEqual(before.level_uid, after.level_uid)
            self.assertEqual(old.source_side, new.source_side)
            self.assertEqual(old.destination_side, new.destination_side)
        self.assertEqual(translate_layout(moved, -101, 23, -11).transitions, self.layout.transitions)

    def test_symbolic_surface_stays_symbolic_during_translation(self):
        level = LocationLevel("floor", self.building.location_uid, 12, 3, "Floor")
        item = physical_transition(self.world.world_uid, "main_entrance", TransitionEndpoint(),
                                   level_endpoint(level, 9, 8, self.building.location_uid), self.building.location_uid)
        layout = StructureLayout([], [level], [item], [])
        moved = translate_layout(layout, 10, 20, -5)
        self.assertIsNone(moved.transitions[0].source.geometry)
        self.assertEqual(moved.transitions[0].destination.geometry, (19, 28, 7))
        self.assert_identity(moved.transitions)

    def test_rebind_keeps_level_uids_and_updates_host_owner_and_identity(self):
        target = replace(self.building, location_uid="final-building")
        bound = rebind_layout_to_building(self.layout, target)
        self.assertEqual([level.level_uid for level in bound.levels], [level.level_uid for level in self.layout.levels])
        self.assert_identity(bound.transitions)
        for item in bound.transitions:
            self.assertEqual(item.destination.host_location_uid, target.location_uid)
            self.assertEqual(item.destination_side.owner_location_uid, target.location_uid)
        validate_transitions(self.world.world_uid, bound.transitions,
            levels={level.level_uid: level for level in bound.levels}, locations={target.location_uid: target},
            nodes={}, registry=WorldTransitionTypeRegistry.canonical_engine())

    def test_passages_are_fresh_outward_snapshots_with_same_uid(self):
        legacy = self.layout.passages
        self.assertIsInstance(legacy, tuple)
        self.assertEqual([item.passage_uid for item in legacy], [item.transition_uid for item in self.layout.transitions])
        legacy[0].to_x = 999
        self.assertNotEqual(self.layout.passages[0].to_x, 999)
        with self.assertRaises(AttributeError):
            self.layout.passages = []
