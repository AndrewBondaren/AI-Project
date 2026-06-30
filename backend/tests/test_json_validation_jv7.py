"""JV-7 — runtime legacy: warn_once + canonical defaults, no silent hardcodes."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.application.worldData.generators.climate.precipitation import (
    resolve_world_precipitation_liquid,
)
from app.application.worldData.generators.terrain.hydrology.loadHydrologyFromWorld import (
    is_hydrology_enabled,
)
from app.application.worldData.generators.terrain.hydrology.resolveRiverTypeClassify import (
    resolve_river_type_classify,
)
from app.application.worldData.generators.utils.tierRegistry import tier_rank
from app.application.worldData.jsonValidation.normalize.hydrologyDefaults import (
    TYPE_CLASSIFY_DEFAULTS,
)


def _world(**kwargs):
    defaults = {
        "world_uid": "jv7-world",
        "precipitation_liquid": "water",
        "material_registry": [
            {
                "system_material": "water",
                "material_category": "liquid",
                "cool_into": "ice",
                "cool_temp": 0,
                "heat_into": "steam",
                "heat_temp": 100,
            },
        ],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestHydrologyRuntimeJv7(unittest.TestCase):

    @patch("app.application.worldData.generators.terrain.hydrology.resolveRiverTypeClassify.warn_once")
    def test_missing_type_classify_warns_and_uses_import_defaults(self, mock_warn):
        w = SimpleNamespace(
            world_uid="w-hydro",
            hydrology={"default_rivers": {}},
        )
        tc = resolve_river_type_classify(w)
        mock_warn.assert_called_once()
        self.assertEqual(tc.mountain_min_source_z, TYPE_CLASSIFY_DEFAULTS["mountain_min_source_z"])

    @patch("app.application.worldData.generators.terrain.hydrology.resolveRiverTypeClassify.warn_once")
    def test_null_type_classify_fields_warn(self, mock_warn):
        w = SimpleNamespace(
            world_uid="w-hydro-null",
            hydrology={
                "default_rivers": {
                    "type_classify": {
                        "mountain_min_source_z": 55,
                        "path_mountain_fraction": None,
                    },
                },
            },
        )
        tc = resolve_river_type_classify(w)
        mock_warn.assert_called_once()
        self.assertEqual(tc.mountain_min_source_z, 55)
        self.assertAlmostEqual(
            tc.path_mountain_fraction,
            float(TYPE_CLASSIFY_DEFAULTS["path_mountain_fraction"]),
        )

    @patch("app.application.worldData.generators.terrain.hydrology.loadHydrologyFromWorld.warn_once")
    def test_implicit_hydrology_enabled_warns(self, mock_warn):
        w = SimpleNamespace(world_uid="w-enabled", hydrology={})
        self.assertTrue(is_hydrology_enabled(w))
        mock_warn.assert_called_once()

    def test_explicit_hydrology_disabled_no_warn(self):
        w = SimpleNamespace(world_uid="w-off", hydrology={"enabled": False})
        with patch(
            "app.application.worldData.generators.terrain.hydrology.loadHydrologyFromWorld.warn_once",
        ) as mock_warn:
            self.assertFalse(is_hydrology_enabled(w))
            mock_warn.assert_not_called()


class TestClimateRuntimeJv7(unittest.TestCase):

    @patch("app.application.worldData.generators.climate.precipitation.warn_once")
    def test_null_precipitation_liquid_warns(self, mock_warn):
        w = _world(precipitation_liquid=None)
        entry = resolve_world_precipitation_liquid(w)
        self.assertEqual(entry.get("system_material"), "water")
        self.assertTrue(any(c.args[1] == "null_precipitation_liquid" for c in mock_warn.call_args_list))

    @patch("app.application.worldData.generators.climate.precipitation.warn_once")
    def test_no_liquid_registry_uses_standalone_water(self, mock_warn):
        w = _world(material_registry=[])
        entry = resolve_world_precipitation_liquid(w)
        self.assertEqual(entry.get("system_material"), "water")
        self.assertTrue(any(c.args[1] == "standalone_water" for c in mock_warn.call_args_list))


class TestTierRuntimeJv7(unittest.TestCase):

    @patch("app.application.worldData.generators.utils.tierRegistry.warn_once")
    def test_unknown_tier_warns(self, mock_warn):
        registry = [{"system_tier": "basic", "base_value": 1}]
        rank = tier_rank(registry, "phantom", world_uid="w-tier")
        self.assertEqual(rank, 0)
        mock_warn.assert_called_once()

    @patch("app.application.worldData.generators.utils.tierRegistry.warn_once")
    def test_unknown_tier_silent_without_world_uid(self, mock_warn):
        registry = [{"system_tier": "basic", "base_value": 1}]
        rank = tier_rank(registry, "phantom")
        self.assertEqual(rank, 0)
        mock_warn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
