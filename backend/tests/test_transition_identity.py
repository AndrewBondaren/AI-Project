"""C3: final physical endpoint identity and preservation across data projections."""

import unittest
from unittest.mock import patch
from uuid import UUID

from app.ids import UidKind, entity_uid, runtime_uid
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry


class TransitionIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = WorldTransitionTypeRegistry.canonical_engine()
        self.system_type = self.registry.require("main_entrance")
        self.source = TransitionEndpoint(x=123, y=-45, z=28)
        self.destination = TransitionEndpoint(space="level", level_uid="level-destination", x=124, y=-45, z=28)

    def test_fixed_key_contract_uses_shared_helper(self) -> None:
        expected_keys = {
            "type": self.system_type,
            "source_space": "surface", "source_x": 123, "source_y": -45, "source_z": 28,
            "source_geometry": "concrete",
            "destination_space": "level", "destination_level_uid": "level-destination",
            "destination_x": 124, "destination_y": -45, "destination_z": 28, "destination_geometry": "concrete",
        }
        with patch(
            "app.application.worldData.transitions.transitionIdentity.entity_uid",
            wraps=entity_uid,
        ) as mint:
            uid = transition_uid("world", self.system_type, self.source, self.destination)
        mint.assert_called_once_with("world", UidKind.TRANSITION, **expected_keys)
        self.assertEqual(uid, entity_uid("world", UidKind.TRANSITION, **expected_keys))
        self.assertEqual(UUID(uid).version, 5)

    def test_repeat_and_wire_field_order_do_not_change_identity(self) -> None:
        uid = transition_uid("world", self.system_type, self.source, self.destination)
        reordered = TransitionEndpoint.model_validate({"z": 28, "y": -45, "x": 123})
        self.assertEqual(uid, transition_uid("world", self.system_type, reordered, self.destination))
        self.assertEqual(uid, transition_uid("world", self.system_type, self.source, self.destination))

    def test_side_order_is_not_sorted_or_discarded(self) -> None:
        self.assertNotEqual(
            transition_uid("world", self.system_type, self.source, self.destination),
            transition_uid("world", self.system_type, self.destination, self.source),
        )

    def test_world_type_and_final_coordinates_distinguish_identity(self) -> None:
        base = transition_uid("world", self.system_type, self.source, self.destination)
        variants = [
            transition_uid("other-world", self.system_type, self.source, self.destination),
            transition_uid("world", self.registry.require("service_entrance"), self.source, self.destination),
        ]
        for side in ("source", "destination"):
            endpoint = self.source if side == "source" else self.destination
            for coordinate in ("x", "y", "z"):
                wire = endpoint.model_dump()
                wire[coordinate] += 10
                moved = TransitionEndpoint.model_validate(wire)
                source, destination = (moved, self.destination) if side == "source" else (self.source, moved)
                variants.append(transition_uid("world", self.system_type, source, destination))
        self.assertNotIn(base, variants)
        self.assertEqual(len(set(variants)), len(variants))

    def test_explicit_refs_and_space_are_identity_inputs(self) -> None:
        endpoints = [
            self.source,
            TransitionEndpoint(x=123, y=-45, z=28, host_location_uid="host-source"),
            TransitionEndpoint(x=123, y=-45, z=28, host_location_uid="host-destination"),
            TransitionEndpoint(x=123, y=-45, z=28, node_uid="node-source"),
            TransitionEndpoint(x=123, y=-45, z=28, node_uid="node-destination"),
            TransitionEndpoint(space="level", level_uid="level-source", x=123, y=-45, z=28),
            TransitionEndpoint(space="level", level_uid="level-destination", x=123, y=-45, z=28),
        ]
        ids = {transition_uid("world", self.system_type, endpoint, self.destination) for endpoint in endpoints}
        self.assertEqual(len(ids), len(endpoints))

    def test_symbolic_surface_marker_has_no_none_or_fake_xyz(self) -> None:
        symbolic = TransitionEndpoint()
        with patch(
            "app.application.worldData.transitions.transitionIdentity.entity_uid",
            wraps=entity_uid,
        ) as mint:
            symbolic_uid = transition_uid("world", self.system_type, symbolic, self.destination)
        keys = mint.call_args.kwargs
        self.assertEqual(keys["source_geometry"], "symbolic")
        self.assertEqual({key for key in keys if key.startswith("source_")},
                         {"source_space", "source_geometry"})
        self.assertNotIn(None, keys.values())
        self.assertNotEqual(symbolic_uid, transition_uid(
            "world", self.system_type, TransitionEndpoint(x=0, y=0, z=0), self.destination,
        ))
        self.assertEqual(symbolic_uid, transition_uid(
            "world", self.system_type,
            TransitionEndpoint.model_validate({"host_location_uid": None, "node_uid": None}), self.destination,
        ))

    def test_custom_system_key_keeps_its_own_identity(self) -> None:
        registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "royal_entry", "display_name": "Вход", "behaves_as": "main_entrance"},
        ])
        custom_key = registry.require("royal_entry")
        self.assertNotEqual(
            transition_uid("world", custom_key, self.source, self.destination),
            transition_uid("world", self.system_type, self.source, self.destination),
        )

    def test_aggregate_and_serialized_projection_preserve_uid_without_remint(self) -> None:
        uid = transition_uid("world", self.system_type, self.source, self.destination)
        aggregate = Transition(
            transition_uid=uid, world_uid="world", system_transition_type=self.system_type,
            source=self.source, destination=self.destination,
        )
        with patch(
            "app.application.worldData.transitions.transitionIdentity.entity_uid",
            side_effect=AssertionError("projections must not mint"),
        ):
            from_mapping = Transition.model_validate(aggregate.model_dump(mode="json"))
            from_json = Transition.model_validate_json(aggregate.model_dump_json())
        self.assertEqual(uid, from_mapping.transition_uid)
        self.assertEqual(uid, from_json.transition_uid)
        changed = Transition.model_validate({
            **aggregate.model_dump(mode="json"),
            "destination_side": {"is_discovered": False, "is_accessible": False,
                       "entry_difficulty_override": 75},
            "display_name": "Новое имя", "is_active": False,
        })
        self.assertEqual(uid, transition_uid(
            changed.world_uid, changed.system_transition_type, changed.source, changed.destination,
        ))

    def test_runtime_creation_uses_existing_random_helper(self) -> None:
        source, destination = runtime_uid(), runtime_uid()
        self.assertNotEqual(source, destination)
        self.assertEqual(UUID(source).version, 4)
        self.assertEqual(UUID(destination).version, 4)


if __name__ == "__main__":
    unittest.main()
