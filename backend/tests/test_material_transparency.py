"""Percentage transparency: numeric boundaries and shared validation policy."""
import math
import unittest
from unittest.mock import patch

from app.application.jsonValidation.resolve import ResolveContext, UnresolvedModelError, resolve_model, resolve_patch
from app.dataModel.materials.materialRegistryEntry import MaterialRegistryEntry
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry


class MaterialTransparencyTests(unittest.TestCase):
    def row(self, **fields):
        return {"system_material": "test_mesh", "display_name": "Test mesh",
                "material_category": "solid", **fields}

    def test_percentages_and_missing_default_roundtrip(self):
        self.assertEqual(resolve_model(MaterialRegistryEntry, self.row()).transparent, 0.0)
        for percent in (0, 1, 42.5, 99.9, 100):
            with self.subTest(percent=percent):
                entry = resolve_model(MaterialRegistryEntry, self.row(transparent=percent))
                self.assertEqual(entry.transparent, percent)
                self.assertEqual(MaterialRegistryEntry.model_validate_json(entry.model_dump_json()), entry)

    def test_invalid_values_have_same_facts_and_mode_specific_logging(self):
        for value in (None, True, False, "50", -1, 100.01, math.nan, math.inf, -math.inf):
            facts = []
            for preview in (False, True):
                ctx = ResolveContext.for_import(validate_only=preview)
                with patch("app.application.jsonValidation.resolve.logger") as log:
                    with self.assertRaises(UnresolvedModelError) as error:
                        resolve_model(MaterialRegistryEntry, self.row(transparent=value), ctx=ctx)
                facts.append([(issue.path, issue.code) for issue in error.exception.issues])
                self.assertEqual(log.warning.call_count, 0 if preview else 1)
            self.assertEqual(facts[0], facts[1])
            self.assertEqual(facts[0][0][0], ("transparent",))

    def test_patch_uses_same_numeric_contract_without_inserting_default(self):
        def ctx():
            return ResolveContext(partial=True, validate_only=True)
        self.assertEqual(resolve_patch(MaterialRegistryEntry, {}, ctx=ctx()), {})
        self.assertEqual(resolve_patch(MaterialRegistryEntry, {"transparent": 37.5}, ctx=ctx()),
                         {"transparent": 37.5})
        for invalid in (True, False, None, "50", -0.1, 101):
            with self.subTest(invalid=invalid), self.assertRaises(UnresolvedModelError):
                resolve_patch(MaterialRegistryEntry, {"transparent": invalid}, ctx=ctx())

    def test_canonical_catalog_uses_percentages(self):
        for registry in (WorldMaterialRegistry.canonical_defaults(), WorldMaterialRegistry.canonical_engine()):
            self.assertEqual(registry.entry_for("window_glass").transparent, 100)
            self.assertEqual(registry.entry_for("porthole_glass").transparent, 100)
            for entry in registry.root:
                self.assertIs(type(entry.transparent), float)
                self.assertTrue(0 <= entry.transparent <= 100)
