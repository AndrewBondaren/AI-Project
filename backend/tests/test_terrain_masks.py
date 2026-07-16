"""Surface mask domains — forest/plains resolve + WorldTerrainMasks (SM-*)."""

from __future__ import annotations

import unittest

from app.application.worldData.masks.resolveForestPlains import resolve_forest_plains
from app.application.worldData.masks.terrainMerge import may_paint_terrain
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.terrainMasks import WorldTerrainMasks


class TestTerrainMasks(unittest.TestCase):
    def setUp(self) -> None:
        self.masks = WorldTerrainMasks.canonical_defaults()
        self.terrain = {
            self.masks.default_plains.system_terrain,
            self.masks.default_forests.system_terrain,
            self.masks.default_mountains.system_terrain,
            self.masks.default_forests.tundra_system_terrain,
        }

    def test_defaults_enabled(self) -> None:
        self.assertTrue(self.masks.enabled)
        self.assertTrue(self.masks.category_enabled(self.masks.default_mountains))

    def test_temperate_wet_is_forest_not_mountain(self) -> None:
        temperate = ClimateZone.TEMPERATE.to_profile()
        key = resolve_forest_plains(
            base_rainfall=temperate.base_rainfall,
            base_temperature=temperate.base_temperature,
            terrain_set=self.terrain,
            forests=self.masks.default_forests,
            plains=self.masks.default_plains,
        )
        self.assertEqual(key, self.masks.default_forests.system_terrain)

    def test_arid_is_plains(self) -> None:
        arid = ClimateZone.ARID.to_profile()
        key = resolve_forest_plains(
            base_rainfall=arid.base_rainfall,
            base_temperature=arid.base_temperature,
            terrain_set=self.terrain,
            forests=self.masks.default_forests,
            plains=self.masks.default_plains,
        )
        self.assertEqual(key, self.masks.default_plains.system_terrain)

    def test_cold_prefers_tundra(self) -> None:
        tundra = ClimateZone.TUNDRA.to_profile()
        key = resolve_forest_plains(
            base_rainfall=tundra.base_rainfall,
            base_temperature=tundra.base_temperature,
            terrain_set=self.terrain,
            forests=self.masks.default_forests,
            plains=self.masks.default_plains,
        )
        self.assertEqual(key, self.masks.default_forests.tundra_system_terrain)

    def test_merge_road_beats_mountain(self) -> None:
        self.assertTrue(
            may_paint_terrain(
                self.masks.default_mountains.system_terrain,
                self.masks.default_roads.system_terrain,
                self.masks,
            )
        )
        self.assertFalse(
            may_paint_terrain(
                self.masks.default_roads.system_terrain,
                self.masks.default_mountains.system_terrain,
                self.masks,
            )
        )


if __name__ == "__main__":
    unittest.main()
