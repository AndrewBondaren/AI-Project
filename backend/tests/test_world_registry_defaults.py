"""Default libraries are resolved by the existing world import/read pipeline."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.jsonValidation.facade import normalize_world
from app.application.jsonValidation.types import ImportValidationError
from app.application.jsonValidation.worldRow import materials, terrain
from app.dataModel.materials.worldMaterialRegistry import WorldMaterialRegistry
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry


class WorldRegistryDefaultsTests(unittest.TestCase):
    def test_missing_and_empty_libraries_are_materialized_on_full_import(self):
        for wire in ({}, {"material_registry": [], "terrain_registry": []}):
            with self.subTest(wire=wire):
                normalized = normalize_world(wire)
                for key, registry in (("material_registry", WorldMaterialRegistry),
                                      ("terrain_registry", WorldTerrainRegistry)):
                    self.assertEqual(normalized[key], registry.canonical_defaults().model_dump(mode="json"))

    def test_partial_library_inherits_fields_and_preserves_explicit_values(self):
        wire = {
            "material_registry": [{"system_material": "wood", "flammable": False,
                                   "heat_conductivity": 0, "hardness": None, "tags": []}],
            "terrain_registry": [{"system_terrain": "shore_river", "default_material": "wood",
                                  "travel_modifier": 0, "has_state": True}],
        }
        normalized = normalize_world(wire)
        stored = json.loads(json.dumps(normalized))
        world = SimpleNamespace(**stored)
        wood = materials(world).entry_for("wood")
        self.assertEqual(wood.model_dump(mode="json"), {
            **WorldMaterialRegistry.canonical_defaults().entry_for("wood").model_dump(mode="json"),
            **wire["material_registry"][0],
        })
        shore = terrain(world).entry_for("shore_river")
        self.assertEqual(shore.model_dump(mode="json"), {
            **WorldTerrainRegistry.canonical_defaults().entry_for("shore_river").model_dump(mode="json"),
            **wire["terrain_registry"][0],
        })
        self.assertIsNotNone(materials(world).entry_for("sand"))
        self.assertIsNotNone(terrain(world).entry_for("shore_sea"))
        legacy = SimpleNamespace(**wire)
        self.assertEqual(materials(legacy), materials(world))
        self.assertEqual(terrain(legacy), terrain(world))

    def test_custom_entries_are_kept_alongside_defaults(self):
        normalized = normalize_world({
            "material_registry": [{"system_material": "custom", "display_name": "Custom",
                                   "material_category": "solid"}],
            "terrain_registry": [{"system_terrain": "custom", "terrain_category": "solid"}],
        })
        world = SimpleNamespace(**normalized)
        self.assertEqual(len(materials(world).root), len(WorldMaterialRegistry.canonical_defaults().root) + 1)
        self.assertEqual(len(terrain(world).root), len(WorldTerrainRegistry.canonical_defaults().root) + 1)
        self.assertEqual(materials(world).entry_for("custom").display_name, "Custom")

    def test_partial_update_without_registry_does_not_materialize_it(self):
        normalized = normalize_world({"name": "Renamed"}, partial=True)
        self.assertEqual(normalized, {"name": "Renamed"})

    def test_registry_normalization_is_idempotent(self):
        once = normalize_world({"material_registry": [{"system_material": "wood", "flammable": False}],
                                "terrain_registry": []}, partial=True)
        twice = normalize_world(json.loads(json.dumps(once)), partial=True)
        self.assertEqual(once, twice)

    def test_unknown_reference_remains_an_import_error(self):
        with self.assertRaisesRegex(ImportValidationError, "unknown REF-W-MATERIAL target: 'missing'"):
            normalize_world({"material_registry": [], "hydrology": {
                "default_rivers": {"shore": {"system_terrain": "shore_river", "system_material": "missing"}},
            }})

    def test_invalid_custom_row_keeps_original_error_index(self):
        with self.assertRaisesRegex(ImportValidationError, r"material_registry\.0\.display_name"):
            normalize_world({"material_registry": [{"system_material": "custom", "material_category": "solid"}]})

    def test_world_test_hydrology_dependencies_are_added_without_fixture_edits(self):
        path = Path(__file__).resolve().parents[2] / "fixtures" / "world_test.json"
        wire = json.loads(path.read_text(encoding="utf-8"))["world"]
        self.assertNotIn("sand", {r["system_material"] for r in wire["material_registry"]})
        normalized = normalize_world(wire)
        self.assertIn("sand", {r["system_material"] for r in normalized["material_registry"]})
        self.assertIn("shore_river", {r["system_terrain"] for r in normalized["terrain_registry"]})


if __name__ == "__main__":
    unittest.main()
