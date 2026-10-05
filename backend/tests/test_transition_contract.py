"""C2 aggregate, geometry, side defaults and physical params contracts."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.dataModel.locations.enums.accessMechanic import AccessMechanic
from app.dataModel.locations.structure.building.levelDef import LevelDef
from app.dataModel.locations.structure.enums.entryAccessType import EntryAccessType
from app.dataModel.locations.structure.enums.staircaseType import StaircaseType
from app.dataModel.locations.transitions.transition import Transition
from app.dataModel.locations.transitions.transitionEndpoint import TransitionEndpoint, TransitionSpace
from app.dataModel.locations.transitions.transitionOrigin import TransitionOrigin
from app.dataModel.locations.transitions.transitionParams import (
    GateTransitionParams, PhysicalTransitionParams, StaircaseTransitionParams,
)
from app.dataModel.locations.transitions.transitionSide import TransitionSide
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry


def _wire(system_type: str = "door", **fields) -> dict:
    return {
        "transition_uid": "transition-1", "world_uid": "world-1",
        "system_transition_type": system_type,
        "source": {"x": 123, "y": -45, "z": 28},
        "destination": {"space": "level", "level_uid": "level-1", "x": 124, "y": -45, "z": 28},
        **fields,
    }


class TransitionContractTest(unittest.TestCase):
    def test_surface_defaults_have_no_fake_geometry_or_location(self) -> None:
        endpoint = TransitionEndpoint()
        self.assertIs(endpoint.space, TransitionSpace.SURFACE)
        self.assertIsNone(endpoint.geometry)
        self.assertIsNone(endpoint.level_uid)
        self.assertIsNone(endpoint.host_location_uid)
        self.assertEqual(endpoint.identity_keys(), {"space": "surface", "geometry": "symbolic"})
        symbolic = Transition.model_validate(_wire(source={}))
        self.assertIsNone(symbolic.source.geometry)
        self.assertIsNone(symbolic.source_side.owner_location_uid)

    def test_concrete_global_geometry_and_identity_refs(self) -> None:
        endpoint = TransitionEndpoint(
            x=123, y=-45, z=28, host_location_uid="root-location", node_uid="node-1",
        )
        self.assertEqual(endpoint.geometry, (123, -45, 28))
        self.assertEqual(endpoint.identity_keys(), {
            "space": "surface", "host_location_uid": "root-location",
            "node_uid": "node-1", "x": 123, "y": -45, "z": 28, "geometry": "concrete",
        })
        self.assertNotEqual(
            TransitionEndpoint().identity_keys(),
            TransitionEndpoint(x=0, y=0, z=0).identity_keys(),
        )

    def test_partial_geometry_and_non_integer_coordinates_are_rejected(self) -> None:
        for wire in ({"x": 1}, {"y": 2, "z": 3}, {"x": 1, "y": 2},
                     {"x": True, "y": 2, "z": 3}, {"x": 1.5, "y": 2, "z": 3},
                     {"x": "1", "y": 2, "z": 3}):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                TransitionEndpoint.model_validate(wire)

    def test_level_requires_ref_and_geometry_surface_disallows_level_ref(self) -> None:
        for wire in ({"space": "level"}, {"space": "level", "level_uid": "l"},
                     {"space": "level", "x": 1, "y": 2, "z": 3},
                     {"level_uid": "l"}, {"space": "wilderness"}, {"host_location_uid": ""}):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                TransitionEndpoint.model_validate(wire)
        self.assertEqual(
            TransitionEndpoint(space="level", level_uid="l", x=1, y=2, z=-3).identity_keys(),
            {"space": "level", "level_uid": "l", "x": 1, "y": 2, "z": -3,
             "geometry": "concrete"},
        )

    def test_two_sides_have_independent_state_and_nullable_owners(self) -> None:
        transition = Transition.model_validate(_wire(
            source_side={"is_accessible": False},
            destination_side={"owner_location_uid": "building", "entry_difficulty_override": 0},
        ))
        self.assertFalse(transition.source_side.is_accessible)
        self.assertTrue(transition.destination_side.is_accessible)
        self.assertIsNone(transition.source_side.owner_location_uid)
        self.assertEqual(transition.destination_side.entry_difficulty_override, 0)
        self.assertIsNone(transition.destination_side.guard_level_override)
        self.assertIsNone(transition.destination.host_location_uid)
        for wire in (_wire(source_side=None), _wire(destination_side=None), _wire(side_c={})):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                Transition.model_validate(wire)

    def test_side_ranges_preserve_none_zero_and_one_hundred(self) -> None:
        for field in ("entry_difficulty_override", "guard_level_override"):
            for value in (None, 0, 100):
                self.assertEqual(getattr(TransitionSide(**{field: value}), field), value)
            for invalid in (-1, 101, True, 1.5):
                with self.subTest(field=field, value=invalid), self.assertRaises(ValidationError):
                    TransitionSide(**{field: invalid})

    def test_hidden_b_default_only_preserves_explicit_discovery_and_access(self) -> None:
        hidden = Transition.model_validate(_wire("hidden_entrance"))
        self.assertTrue(hidden.source_side.is_discovered)
        self.assertFalse(hidden.destination_side.is_discovered)
        self.assertTrue(hidden.destination_side.is_accessible)
        explicit = Transition.model_validate(_wire(
            "hidden_entrance", destination_side={"is_discovered": True, "is_accessible": False},
        ))
        self.assertTrue(explicit.destination_side.is_discovered)
        self.assertFalse(explicit.destination_side.is_accessible)

    def test_direction_defaults_and_fall_access_state(self) -> None:
        door = Transition.model_validate(_wire())
        self.assertTrue(door.is_bidirectional)
        self.assertTrue(door.is_active)
        fall = Transition.model_validate(_wire("fall", destination_side={"is_accessible": False}))
        self.assertFalse(fall.is_bidirectional)
        self.assertFalse(fall.destination_side.is_accessible)
        for wire in (_wire(is_bidirectional=False), _wire("fall", is_bidirectional=True)):
            with self.assertRaises(ValidationError):
                Transition.model_validate(wire)

    def test_physical_params_are_typed_and_strict(self) -> None:
        staircase = Transition.model_validate(_wire(
            "staircase", type_params={"staircase_type": "spiral"},
        ))
        self.assertIsInstance(staircase.type_params, StaircaseTransitionParams)
        self.assertIs(staircase.type_params.staircase_type, StaircaseType.SPIRAL)
        default = Transition.model_validate(_wire("staircase"))
        self.assertIs(default.type_params.staircase_type, StaircaseType.generator_default())
        gate = Transition.model_validate(_wire("gate", type_params={"width_cells": 2}))
        self.assertIsInstance(gate.type_params, GateTransitionParams)
        self.assertEqual(gate.type_params.width_cells, 2)
        self.assertIsInstance(Transition.model_validate(_wire()).type_params, PhysicalTransitionParams)
        for wire in (_wire("gate"), _wire("gate", type_params={"width_cells": 0}),
                     _wire("gate", type_params={"width_cells": True}),
                     _wire("staircase", type_params={"staircase_type": "unknown"}),
                     _wire(type_params={"width_cells": 2}), _wire(type_params={"unknown": 2})):
            with self.subTest(wire=wire), self.assertRaises(ValidationError):
                Transition.model_validate(wire)

    def test_custom_types_use_caller_registry_for_params_and_defaults(self) -> None:
        registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "secret_stair", "display_name": "Тайный вход", "behaves_as": "hidden_entrance"},
            {"system_type": "iron_gate", "display_name": "Калитка", "behaves_as": "gate"},
        ])
        context = {"transition_type_registry": registry}
        hidden = Transition.model_validate(_wire("secret_stair"), context=context)
        self.assertFalse(hidden.destination_side.is_discovered)
        gate = Transition.model_validate(
            _wire("iron_gate", type_params={"width_cells": 3}), context=context,
        )
        self.assertIsInstance(gate.type_params, GateTransitionParams)
        restored = Transition.model_validate_json(gate.model_dump_json(), context=context)
        self.assertEqual(gate, restored)
        with self.assertRaises(ValidationError):
            Transition.model_validate(_wire("secret_stair"))

    def test_portal_projection_is_explicitly_deferred(self) -> None:
        with self.assertRaisesRegex(ValidationError, "PORTAL-T-1"):
            Transition.model_validate(_wire("portal"))

    def test_roundtrip_keeps_every_field_and_typed_params(self) -> None:
        transition = Transition.model_validate(_wire(
            "staircase", origin="runtime", is_active=False,
            access_mechanic=["key", "lockpick"],
            type_params={"staircase_type": "u_shape"},
            display_name="Лестница", glossary_ref="stair_lore", tag_refs=["stone"],
            source_side={"owner_location_uid": "room-source", "is_discovered": False,
                    "entry_difficulty_override": 100, "display_name": "Нижний выход"},
            destination_side={"owner_location_uid": "room-destination", "is_accessible": False,
                    "guard_level_override": 0},
        ))
        wire = transition.model_dump(mode="json")
        self.assertEqual(wire["type_params"], {"staircase_type": "u_shape"})
        self.assertEqual(wire["access_mechanic"], ["key", "lockpick"])
        self.assertIs(transition.origin, TransitionOrigin.RUNTIME)
        self.assertEqual(Transition.model_validate_json(transition.model_dump_json()), transition)
        self.assertEqual(Transition.model_validate(wire), transition)

    def test_access_mechanics_shared_with_levels_are_not_entry_approaches(self) -> None:
        for member in AccessMechanic:
            transition = Transition.model_validate(_wire(access_mechanic=[member.value]))
            self.assertIs(transition.access_mechanic[0], member)
        self.assertEqual(Transition.model_validate(_wire()).access_mechanic, [])
        for invalid in ("unknown", EntryAccessType.PORCH):
            with self.assertRaises(ValidationError):
                Transition.model_validate(_wire(access_mechanic=[invalid]))
        from pydantic import TypeAdapter
        adapter = TypeAdapter(LevelDef.model_fields["access_mechanic"].annotation)
        self.assertEqual(adapter.validate_python(["excavation", "teleport"]),
                         [AccessMechanic.EXCAVATION, AccessMechanic.TELEPORT])
        with self.assertRaises(ValidationError):
            adapter.validate_python(["unknown"])

    def test_identity_is_separate_from_state_and_keeps_a_b_order(self) -> None:
        transition = Transition.model_validate(_wire())
        changed = Transition.model_validate(_wire(source_side={"is_discovered": False}))
        self.assertEqual(transition.source.identity_keys(), changed.source.identity_keys())
        self.assertNotEqual(transition.source.identity_keys(), transition.destination.identity_keys())
        self.assertFalse(any(value is None for value in transition.source.identity_keys().values()))


if __name__ == "__main__":
    unittest.main()
