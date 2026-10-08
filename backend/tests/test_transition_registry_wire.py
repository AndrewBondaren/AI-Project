"""P3: transition registry uses the shared WorldSlice import/runtime policies."""

from app.application.jsonValidation.resolve import UnresolvedModelError, ResolveContext, resolve_result
import unittest
from types import SimpleNamespace

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import transition_types
from app.application.jsonValidation.worldSlices import WORLD_SLICES, slice_for_pojo
from app.dataModel.locations.transitions.transitionType import TransitionType
from app.dataModel.locations.transitions.worldTransitionTypeRegistry import WorldTransitionTypeRegistry
from app.db.models.world import World


def _row(key="custom", behaves_as="door"):
    return {"system_type": key, "display_name": "Проход", "behaves_as": behaves_as,
            "glossary_ref": None}


class TransitionRegistryWireTest(unittest.TestCase):
    def test_single_slice_uses_pojo_schema_and_defaults(self) -> None:
        matches = [sl for sl in WORLD_SLICES if sl.pojo_cls is WorldTransitionTypeRegistry]
        self.assertEqual(len(matches), 1)
        sl = slice_for_pojo(WorldTransitionTypeRegistry)
        self.assertTrue(sl.facade)
        self.assertEqual(sl.world_keys, ("transition_type_registry",))
        self.assertEqual(sl.schema_id, WorldTransitionTypeRegistry.SCHEMA_ID)
        self.assertEqual(sl.empty_factory(), WorldTransitionTypeRegistry.canonical_defaults())
        self.assertIsNone(sl.wire_adapter)

    def test_import_canonical_and_custom_roundtrip(self) -> None:
        for rows in (WorldTransitionTypeRegistry.canonical_engine().model_dump(mode="json"),
                     [_row("royal_entry", "main_entrance"), _row("hidden_door", "hidden_entrance")]):
            with self.subTest(rows=rows):
                normalized = normalize_world({"transition_type_registry": rows}, partial=True)
                world = World(world_uid="world", name="W", created_at="2026-10-06", **normalized)
                registry = transition_types(world)
                self.assertEqual(registry.model_dump(mode="json"), normalized["transition_type_registry"])
        self.assertIs(registry.type_for("royal_entry"), TransitionType.MAIN_ENTRANCE)
        self.assertTrue(registry.entry_for("hidden_door").entry)

    def test_import_empty_is_canonical_absent_is_untouched(self) -> None:
        self.assertNotIn("transition_type_registry", normalize_world({}, partial=True))
        normalized = normalize_world({"transition_type_registry": []}, partial=True)
        self.assertEqual(normalized["transition_type_registry"],
                         WorldTransitionTypeRegistry.canonical_defaults().model_dump(mode="json"))

    def test_runtime_absent_empty_and_null_use_canonical(self) -> None:
        for world in (SimpleNamespace(world_uid="w"),
                      SimpleNamespace(world_uid="w", transition_type_registry=[]),
                      SimpleNamespace(world_uid="w", transition_type_registry=None)):
            self.assertEqual(transition_types(world), WorldTransitionTypeRegistry.canonical_defaults())

    def test_import_requires_behaves_as_with_precise_path(self) -> None:
        row = _row()
        del row["behaves_as"]
        with self.assertRaises(ImportValidationError) as caught:
            normalize_world({"transition_type_registry": [row]}, partial=True)
        errors = caught.exception.errors
        self.assertTrue(any(error.path == ("transition_type_registry", 0, "behaves_as")
                            and error.schema_id == WorldTransitionTypeRegistry.SCHEMA_ID for error in errors))

    def test_import_unknown_builtin_is_strict_and_path_is_indexed(self) -> None:
        for unknown in ("unknown", "graph", "coordinate"):
            with self.subTest(unknown=unknown), self.assertRaises(ImportValidationError) as caught:
                normalize_world({"transition_type_registry": [_row("valid"), _row("bad", unknown)]}, partial=True)
            self.assertTrue(any(error.path == ("transition_type_registry", 1, "behaves_as")
                                and error.code == "UNKNOWN_ENUM" for error in caught.exception.errors))

    def test_import_wrong_identity_type_and_registry_shape(self) -> None:
        for value, path in (([_row(42)], ("transition_type_registry", 0, "system_type")),
                            ([42], ("transition_type_registry", 0)),
                            ({"door": _row()}, ("transition_type_registry",))):
            with self.subTest(value=value), self.assertRaises(ImportValidationError) as caught:
                normalize_world({"transition_type_registry": value}, partial=True)
            self.assertTrue(any(error.path == path for error in caught.exception.errors))

    def test_runtime_invalid_row_rejects_whole_registry(self):
        for bad in (_row("bad", "unknown"), {"system_type": "bad", "display_name": "Bad"}):
            with self.subTest(bad=bad), self.assertLogs("app.application.jsonValidation.resolve", "WARNING"), self.assertRaises(UnresolvedModelError):
                transition_types(SimpleNamespace(world_uid="world", transition_type_registry=[_row("valid"), bad]))

    def test_builtin_behavior_cannot_be_reassigned_through_facade(self) -> None:
        with self.assertRaises(ImportValidationError) as caught:
            normalize_world({"transition_type_registry": [_row("main_entrance", "door")]}, partial=True)
        self.assertTrue(any(error.path == ("transition_type_registry", 0) for error in caught.exception.errors))

    def test_runtime_reassigned_builtin_rejects_whole_registry(self):
        with self.assertLogs("app.application.jsonValidation.resolve", "WARNING"), self.assertRaises(UnresolvedModelError):
            transition_types(SimpleNamespace(world_uid="world", transition_type_registry=[_row("valid"), _row("main_entrance", "door")]))

    def test_deferred_portal_registry_is_not_converted(self) -> None:
        data = {"connection_type_registry": [{"system_connection_type": "portal", "display_name": "Портал"}],
                "transition_type_registry": [_row()]}
        normalized = normalize_world(data, partial=True)
        self.assertEqual(normalized["connection_type_registry"], data["connection_type_registry"])


if __name__ == "__main__":
    unittest.main()
