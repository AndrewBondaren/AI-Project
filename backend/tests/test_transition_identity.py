"""C3: final physical endpoint identity and preservation across data projections."""

import unittest
from unittest.mock import patch
from uuid import UUID

from app.application.worldData.ids import UidKind, entity_uid, runtime_uid
from app.application.worldData.transitions.transitionIdentity import transition_uid
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry


class TransitionIdentityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = WorldTransitionTypeRegistry.canonical_engine()
        self.system_type = self.registry.require("main_entrance")
        self.a = TransitionEndpoint(x=123, y=-45, z=28)
        self.b = TransitionEndpoint(space="level", level_uid="level-b", x=124, y=-45, z=28)

    def test_fixed_key_contract_uses_shared_helper(self) -> None:
        expected_keys = {
            "type": self.system_type,
            "a_space": "surface", "a_x": 123, "a_y": -45, "a_z": 28,
            "a_geometry": "concrete",
            "b_space": "level", "b_level_uid": "level-b",
            "b_x": 124, "b_y": -45, "b_z": 28, "b_geometry": "concrete",
        }
        with patch(
            "app.application.worldData.transitions.transitionIdentity.entity_uid",
            wraps=entity_uid,
        ) as mint:
            uid = transition_uid("world", self.system_type, self.a, self.b)
        mint.assert_called_once_with("world", UidKind.TRANSITION, **expected_keys)
        self.assertEqual(uid, entity_uid("world", UidKind.TRANSITION, **expected_keys))
        self.assertEqual(UUID(uid).version, 5)

    def test_repeat_and_wire_field_order_do_not_change_identity(self) -> None:
        uid = transition_uid("world", self.system_type, self.a, self.b)
        reordered = TransitionEndpoint.model_validate({"z": 28, "y": -45, "x": 123})
        self.assertEqual(uid, transition_uid("world", self.system_type, reordered, self.b))
        self.assertEqual(uid, transition_uid("world", self.system_type, self.a, self.b))

    def test_side_order_is_not_sorted_or_discarded(self) -> None:
        self.assertNotEqual(
            transition_uid("world", self.system_type, self.a, self.b),
            transition_uid("world", self.system_type, self.b, self.a),
        )

    def test_world_type_and_final_coordinates_distinguish_identity(self) -> None:
        base = transition_uid("world", self.system_type, self.a, self.b)
        variants = [
            transition_uid("other-world", self.system_type, self.a, self.b),
            transition_uid("world", self.registry.require("service_entrance"), self.a, self.b),
        ]
        for side in ("a", "b"):
            endpoint = self.a if side == "a" else self.b
            for coordinate in ("x", "y", "z"):
                wire = endpoint.model_dump()
                wire[coordinate] += 10
                moved = TransitionEndpoint.model_validate(wire)
                a, b = (moved, self.b) if side == "a" else (self.a, moved)
                variants.append(transition_uid("world", self.system_type, a, b))
        self.assertNotIn(base, variants)
        self.assertEqual(len(set(variants)), len(variants))

    def test_explicit_refs_and_space_are_identity_inputs(self) -> None:
        endpoints = [
            self.a,
            TransitionEndpoint(x=123, y=-45, z=28, host_location_uid="host-a"),
            TransitionEndpoint(x=123, y=-45, z=28, host_location_uid="host-b"),
            TransitionEndpoint(x=123, y=-45, z=28, node_uid="node-a"),
            TransitionEndpoint(x=123, y=-45, z=28, node_uid="node-b"),
            TransitionEndpoint(space="level", level_uid="level-a", x=123, y=-45, z=28),
            TransitionEndpoint(space="level", level_uid="level-b", x=123, y=-45, z=28),
        ]
        ids = {transition_uid("world", self.system_type, endpoint, self.b) for endpoint in endpoints}
        self.assertEqual(len(ids), len(endpoints))

    def test_symbolic_surface_marker_has_no_none_or_fake_xyz(self) -> None:
        symbolic = TransitionEndpoint()
        with patch(
            "app.application.worldData.transitions.transitionIdentity.entity_uid",
            wraps=entity_uid,
        ) as mint:
            symbolic_uid = transition_uid("world", self.system_type, symbolic, self.b)
        keys = mint.call_args.kwargs
        self.assertEqual(keys["a_geometry"], "symbolic")
        self.assertEqual({key for key in keys if key.startswith("a_")},
                         {"a_space", "a_geometry"})
        self.assertNotIn(None, keys.values())
        self.assertNotEqual(symbolic_uid, transition_uid(
            "world", self.system_type, TransitionEndpoint(x=0, y=0, z=0), self.b,
        ))
        self.assertEqual(symbolic_uid, transition_uid(
            "world", self.system_type,
            TransitionEndpoint.model_validate({"host_location_uid": None, "node_uid": None}), self.b,
        ))

    def test_custom_system_key_keeps_its_own_identity(self) -> None:
        registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "royal_entry", "display_name": "Вход", "behaves_as": "main_entrance"},
        ])
        custom_key = registry.require("royal_entry")
        self.assertNotEqual(
            transition_uid("world", custom_key, self.a, self.b),
            transition_uid("world", self.system_type, self.a, self.b),
        )

    def test_aggregate_and_serialized_projection_preserve_uid_without_remint(self) -> None:
        uid = transition_uid("world", self.system_type, self.a, self.b)
        aggregate = Transition(
            transition_uid=uid, world_uid="world", system_transition_type=self.system_type,
            a=self.a, b=self.b,
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
            "side_b": {"is_discovered": False, "is_accessible": False,
                       "entry_difficulty_override": 75},
            "display_name": "Новое имя", "is_active": False,
        })
        self.assertEqual(uid, transition_uid(
            changed.world_uid, changed.system_transition_type, changed.a, changed.b,
        ))

    def test_runtime_creation_uses_existing_random_helper(self) -> None:
        a, b = runtime_uid(), runtime_uid()
        self.assertNotEqual(a, b)
        self.assertEqual(UUID(a).version, 4)
        self.assertEqual(UUID(b).version, 4)


if __name__ == "__main__":
    unittest.main()
