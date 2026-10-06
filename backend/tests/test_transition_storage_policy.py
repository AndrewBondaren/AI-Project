"""V1 reference snapshots and explicit building scope storage decisions."""

import unittest
from dataclasses import replace

from app.application.worldData.transitions.transitionStoragePolicy import (
    BuildingTransitionScope, partition_transitions,
)
from app.application.worldData.transitions.transitionValidation import (
    TransitionValidationError, validate_transitions,
)
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.models.connectionNode import ConnectionNode
from app.db.models.locationLevel import LocationLevel
from app.db.models.namedLocation import NamedLocation


class TransitionStoragePolicyTest(unittest.TestCase):
    def setUp(self):
        self.registry = WorldTransitionTypeRegistry.canonical_engine()
        self.locations = {
            uid: NamedLocation(uid, "world", uid, "building", "2026-10-06",
                               parent_location_uid=parent)
            for uid, parent in (("house", "district"), ("neighbor", "other-district"),
                                ("cave", "forest"), ("room", "house"), ("root", None))
        }
        self.levels = {
            "floor": LocationLevel("floor", "house", 28, 3, "Floor"),
            "upper": LocationLevel("upper", "house", 31, 3, "Upper"),
            "neighbor-floor": LocationLevel("neighbor-floor", "neighbor", 28, 3, "Floor"),
            "cave-floor": LocationLevel("cave-floor", "cave", 25, 3, "Cave"),
        }
        self.nodes = {"node": ConnectionNode("node", 100, -45, 28, "building_entrance", "area", "world")}

    def endpoint(self, level="floor", **wire):
        return TransitionEndpoint(space="level", level_uid=level, x=100, y=-45,
                                  z=self.levels[level].z, **wire)

    def transition(self, uid="t", system_type="door", source=None, destination=None, **wire):
        return Transition.model_validate({
            "transition_uid": uid, "world_uid": "world", "system_transition_type": system_type,
            "source": source if source is not None else self.endpoint(),
            "destination": destination if destination is not None else self.endpoint(),
            **wire,
        }, context={"transition_type_registry": self.registry})

    def validate(self, transitions, **overrides):
        validate_transitions("world", transitions, levels=overrides.get("levels", self.levels),
                             locations=overrides.get("locations", self.locations),
                             nodes=overrides.get("nodes", self.nodes), registry=self.registry)

    def scope(self, *transitions, building="house", levels=None):
        return BuildingTransitionScope(building, frozenset(levels or ("floor", "upper")),
                                       frozenset(t.transition_uid for t in transitions))

    def partition(self, transitions, *scopes):
        self.validate(transitions)
        return partition_transitions(transitions, building_scopes=scopes, registry=self.registry)

    def test_materialized_interior_door_and_staircase_go_to_pack(self):
        door = self.transition("door", source_side={"owner_location_uid": "room"},
                               destination_side={"owner_location_uid": "house"})
        stairs = self.transition("stairs", "staircase", destination=self.endpoint("upper"))
        result = self.partition([door, stairs], self.scope(door, stairs))
        self.assertEqual(result.sql_transitions, ())
        self.assertEqual(result.pack_by_building, {"house": (door, stairs)})

    def test_same_owner_or_level_does_not_establish_layout_membership(self):
        door = self.transition(source_side={"owner_location_uid": "house"},
                               destination_side={"owner_location_uid": "house"})
        for scopes in ([], [self.scope()]):
            result = partition_transitions([door], building_scopes=scopes, registry=self.registry)
            self.assertEqual(result.sql_transitions, (door,))
            self.assertEqual(result.pack_by_building, {})

    def test_neighboring_buildings_are_sql_despite_equal_coordinates(self):
        door = self.transition(destination=self.endpoint("neighbor-floor"))
        result = self.partition([door], self.scope(door))
        self.assertEqual(result.sql_transitions, (door,))

    def test_cross_branch_hatch_is_valid_sql_and_parents_are_unchanged(self):
        hatch = self.transition(system_type="hatch", destination=self.endpoint("cave-floor"),
                                source_side={"owner_location_uid": "house"},
                                destination_side={"owner_location_uid": "cave"})
        before = {uid: row.parent_location_uid for uid, row in self.locations.items()}
        result = self.partition([hatch], self.scope(hatch))
        self.assertEqual(result.sql_transitions, (hatch,))
        self.assertEqual(before, {uid: row.parent_location_uid for uid, row in self.locations.items()})

    def test_surface_without_nl_and_symbolic_exit_remain_sql(self):
        for endpoint in (TransitionEndpoint(), TransitionEndpoint(x=101, y=-45, z=28)):
            door = self.transition(source=endpoint)
            result = self.partition([door], self.scope(door))
            self.assertEqual(result.sql_transitions, (door,))
            self.assertIsNone(door.source_side.owner_location_uid)
            self.assertIsNone(door.source.host_location_uid)
        gate = self.transition(system_type="gate", source=TransitionEndpoint(x=1, y=2, z=7),
                               destination=TransitionEndpoint(x=2, y=2, z=7),
                               type_params={"width_cells": 1})
        self.assertEqual(self.partition([gate]).sql_transitions, (gate,))

    def test_runtime_and_directional_are_sql_inside_explicit_scope(self):
        breach = self.transition("runtime", "breach", origin="runtime")
        fall = self.transition("fall", "fall", source=self.endpoint("upper"),
                               destination_side={"is_accessible": False})
        result = self.partition([breach, fall], self.scope(breach, fall))
        self.assertEqual(result.sql_transitions, (breach, fall))
        self.assertEqual(result.pack_by_building, {})
        self.assertFalse(fall.destination_side.is_accessible)

    def test_custom_behaves_as_controls_storage_and_vertical_validation(self):
        self.registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "secret_ladder", "display_name": "Лестница", "behaves_as": "ladder"},
            {"system_type": "trap", "display_name": "Ловушка", "behaves_as": "fall"},
        ])
        ladder = self.transition("ladder", "secret_ladder", destination=self.endpoint("upper"))
        fall = self.transition("fall", "trap", source=self.endpoint("upper"))
        result = self.partition([ladder, fall], self.scope(ladder, fall))
        self.assertEqual(result.pack_by_building, {"house": (ladder,)})
        self.assertEqual(result.sql_transitions, (fall,))

    def test_missing_location_level_node_and_world_mismatches_fail(self):
        door = self.transition(source=self.endpoint(node_uid="node", host_location_uid="house"),
                               destination_side={"owner_location_uid": "room"})
        self.validate([door])
        bad_levels = {**self.levels, "floor": replace(self.levels["floor"], location_uid="missing")}
        other_locations = {**self.locations, "house": replace(self.locations["house"], world_uid="other")}
        other_nodes = {"node": replace(self.nodes["node"], world_uid="other")}
        for overrides in ({"levels": {}}, {"nodes": {}},
                          {"locations": {}}, {"levels": bad_levels},
                          {"locations": other_locations}, {"nodes": other_nodes}):
            with self.subTest(overrides=overrides), self.assertRaises(TransitionValidationError):
                self.validate([door], **overrides)
        with self.assertRaisesRegex(TransitionValidationError, "another world"):
            self.validate([door.model_copy(update={"world_uid": "other"})])

    def test_level_host_z_and_node_geometry_must_agree(self):
        for endpoint in (self.endpoint(host_location_uid="neighbor"),
                         self.endpoint(node_uid="node").model_copy(update={"x": 101}),
                         self.endpoint().model_copy(update={"z": 31}),
                         TransitionEndpoint(node_uid="node")):
            with self.subTest(endpoint=endpoint), self.assertRaises(TransitionValidationError):
                self.validate([self.transition(source=endpoint)])
        # A concrete endpoint can lie above the floor within the actual level height.
        upper_point = self.endpoint().model_copy(update={"z": 29})
        self.validate([self.transition(source=upper_point, destination=upper_point)])

    def test_nullable_ownership_root_host_and_no_discovery_policy(self):
        door = self.transition(source=TransitionEndpoint(x=100, y=-45, z=28, host_location_uid="root"),
                               destination_side={"is_discovered": False, "is_accessible": False},
                               is_active=False, access_mechanic=["key"])
        self.validate([door])
        self.assertFalse(door.destination_side.is_accessible)
        self.assertFalse(door.destination_side.is_discovered)
        self.assertIsNone(self.locations["root"].parent_location_uid)

    def test_vertical_metadata_and_complete_aggregate_are_revalidated(self):
        invalid = [self.transition(system_type="door", destination=self.endpoint("upper")),
                   self.transition(system_type="staircase"),
                   self.transition(system_type="fall", destination=self.endpoint("upper"))]
        valid = self.transition()
        invalid += [valid.model_copy(update={"source": self.endpoint().model_copy(update={"y": None})}),
                    valid.model_copy(update={"is_bidirectional": False}),
                    valid.model_copy(update={"system_transition_type": "missing"})]
        for transition in invalid:
            with self.subTest(transition=transition), self.assertRaises(TransitionValidationError):
                self.validate([transition])

    def test_ambiguous_layout_scopes_are_rejected(self):
        door = self.transition()
        for scopes in ([self.scope(door), self.scope(door)],
                       [self.scope(door), self.scope(door, building="neighbor")]):
            with self.assertRaises(ValueError):
                partition_transitions([door], building_scopes=scopes, registry=self.registry)

    def test_partition_preserves_input_objects_and_order(self):
        packed1, sql, packed2 = self.transition("one"), self.transition("two", origin="runtime"), self.transition("three")
        result = self.partition([packed1, sql, packed2], self.scope(packed1, sql, packed2))
        self.assertEqual(result.pack_by_building["house"], (packed1, packed2))
        self.assertIs(result.sql_transitions[0], sql)
        self.assertIs(result.pack_by_building["house"][0], packed1)


if __name__ == "__main__":
    unittest.main()
