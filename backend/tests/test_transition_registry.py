"""C1: builtin transition metadata and typed N+1 behavior delegation."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.dataModel.annotationPolicy import WireFieldPolicy, field_policy, wire_enum_class
from app.dataModel.locations.transitions.transitionType import TransitionType, TransitionVertical
from app.dataModel.locations.transitions.transitionTypeEntry import TransitionTypeEntry
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import (
    TransitionTypeKey,
    WorldTransitionTypeRegistry,
)
from app.dataModel.registryKey import RegistryKey, registry_key_target


class TransitionRegistryTest(unittest.TestCase):
    def test_canonical_registry_covers_builtin_vocabulary(self) -> None:
        registry = WorldTransitionTypeRegistry.canonical_engine()
        self.assertEqual(len(registry.root), 17)
        self.assertEqual(registry.keys(), frozenset(TransitionType))
        self.assertEqual(registry, WorldTransitionTypeRegistry.canonical_defaults())
        for member in TransitionType:
            with self.subTest(member=member):
                entry = registry.entry_for(member)
                self.assertIsNotNone(entry)
                self.assertIsInstance(entry.system_type, RegistryKey)
                self.assertIs(entry.behaves_as, member)
                self.assertIs(entry.spec, member.spec)
                self.assertEqual(entry.entry, member.entry)
                self.assertEqual(entry.directional, member.directional)
                self.assertIs(entry.vertical, member.vertical)

    def test_builtin_metadata_matches_specification(self) -> None:
        self.assertEqual(
            {member for member in TransitionType if member.entry},
            {TransitionType.MAIN_ENTRANCE, TransitionType.SERVICE_ENTRANCE,
             TransitionType.HIDDEN_ENTRANCE},
        )
        self.assertEqual(
            {member for member in TransitionType if member.directional},
            {TransitionType.PORTAL, TransitionType.FALL},
        )
        expected = {
            TransitionVertical.NONE: {
                TransitionType.MAIN_ENTRANCE, TransitionType.SERVICE_ENTRANCE,
                TransitionType.DOOR, TransitionType.DOORWAY, TransitionType.ARCHWAY,
                TransitionType.CORRIDOR, TransitionType.GATE, TransitionType.BRIDGE,
            },
            TransitionVertical.REQUIRED: {
                TransitionType.STAIRCASE, TransitionType.LADDER,
                TransitionType.ROPE, TransitionType.HATCH,
            },
            TransitionVertical.ANY: {
                TransitionType.HIDDEN_ENTRANCE, TransitionType.TUNNEL,
                TransitionType.BREACH, TransitionType.PORTAL,
            },
            TransitionVertical.DOWN: {TransitionType.FALL},
        }
        for vertical, members in expected.items():
            with self.subTest(vertical=vertical):
                self.assertEqual(
                    {member for member in TransitionType if member.vertical == vertical},
                    members,
                )

    def test_custom_display_types_use_builtin_behavior(self) -> None:
        registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "royal_door", "display_name": "Царские врата",
             "behaves_as": "main_entrance"},
            {"system_type": "servants_door", "display_name": "Вход слуг",
             "behaves_as": "service_entrance"},
            {"system_type": "secret_stair", "display_name": "Тайная лестница",
             "behaves_as": "hidden_entrance"},
            {"system_type": "magic_mirror", "display_name": "Зеркало",
             "behaves_as": "portal"},
        ])
        for key, builtin in (
            ("royal_door", TransitionType.MAIN_ENTRANCE),
            ("servants_door", TransitionType.SERVICE_ENTRANCE),
            ("secret_stair", TransitionType.HIDDEN_ENTRANCE),
            ("magic_mirror", TransitionType.PORTAL),
        ):
            with self.subTest(key=key):
                self.assertIs(registry.type_for(key), builtin)
                self.assertIs(registry.entry_for(key).spec, builtin.spec)
        self.assertEqual(registry.require("royal_door"), "royal_door")

    def test_behaves_as_is_required_even_for_builtin_keys(self) -> None:
        for key in ("door", "ornate_door"):
            with self.subTest(key=key), self.assertRaises(ValidationError) as caught:
                WorldTransitionTypeRegistry.model_validate([
                    {"system_type": key, "display_name": "Дверь"},
                ])
            self.assertEqual(caught.exception.errors()[0]["loc"], (0, "behaves_as"))

    def test_unknown_builtin_and_portal_implementations_are_rejected(self) -> None:
        for key in ("unknown", "graph", "coordinate", "", None):
            with self.subTest(key=key), self.assertRaises(ValidationError) as caught:
                WorldTransitionTypeRegistry.model_validate([
                    {"system_type": "custom", "display_name": "Custom", "behaves_as": key},
                ])
            self.assertEqual(caught.exception.errors()[0]["loc"], (0, "behaves_as"))
        for key in ("graph", "coordinate", "unknown"):
            with self.subTest(enum=key), self.assertRaises(ValueError):
                TransitionType(key)

    def test_builtin_key_cannot_be_reassigned(self) -> None:
        with self.assertRaises(ValidationError):
            WorldTransitionTypeRegistry.model_validate([
                {"system_type": "main_entrance", "display_name": "Вход",
                 "behaves_as": "door"},
            ])

    def test_wire_flags_cannot_override_builtin_metadata(self) -> None:
        registry = WorldTransitionTypeRegistry.model_validate([
            {"system_type": "ornate_door", "display_name": "Дверь", "behaves_as": "door",
             "entry": True, "directional": True, "vertical": "down"},
        ])
        entry = registry.root[0]
        self.assertFalse(entry.entry)
        self.assertFalse(entry.directional)
        self.assertIs(entry.vertical, TransitionVertical.NONE)
        self.assertNotIn("entry", entry.model_dump(mode="json"))

    def test_wire_policies_and_nominal_identity(self) -> None:
        self.assertIs(
            registry_key_target(TransitionTypeEntry.model_fields["system_type"].annotation),
            WorldTransitionTypeRegistry,
        )
        self.assertIs(registry_key_target(TransitionTypeKey), WorldTransitionTypeRegistry)
        annotation = TransitionTypeEntry.model_fields["behaves_as"].annotation
        self.assertIs(field_policy(annotation), WireFieldPolicy.STRICT_ON_WIRE)
        self.assertIs(wire_enum_class(annotation), TransitionType)
        for invalid in ("", None, 42):
            with self.subTest(key=invalid), self.assertRaises(ValidationError):
                WorldTransitionTypeRegistry.model_validate([
                    {"system_type": invalid, "display_name": "Дверь", "behaves_as": "door"},
                ])

    def test_json_roundtrip_preserves_custom_and_canonical_rows(self) -> None:
        registry = WorldTransitionTypeRegistry.canonical_engine()
        registry.root.append(TransitionTypeEntry(
            system_type="silver_gate", display_name="Серебряные ворота",
            behaves_as=TransitionType.GATE, glossary_ref="silver_gate_lore",
        ))
        restored = WorldTransitionTypeRegistry.model_validate_json(registry.model_dump_json())
        self.assertEqual(registry, restored)
        self.assertIs(restored.type_for("silver_gate"), TransitionType.GATE)
        self.assertEqual(restored.entry_for("silver_gate").glossary_ref, "silver_gate_lore")
        self.assertEqual(len(WorldTransitionTypeRegistry.canonical_engine().root), 17)

    def test_missing_lookup_has_no_invented_behavior(self) -> None:
        registry = WorldTransitionTypeRegistry.canonical_engine()
        self.assertIsNone(registry.entry_for("missing"))
        self.assertIsNone(registry.type_for("missing"))
        with self.assertRaisesRegex(RuntimeError, "missing"):
            registry.require("missing")


if __name__ == "__main__":
    unittest.main()
