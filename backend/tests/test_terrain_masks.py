"""Surface mask domains — forest/plains resolve + WorldTerrainMasks (SM-*)."""

from __future__ import annotations

import unittest

from app.application.worldData.masks.resolveForestPlains import resolve_forest_plains
from app.application.worldData.masks.terrainMerge import may_paint_terrain
from app.application.worldData.pack.bake.lightGrid.maskDomainRegistry import (
    build_default_contributors,
)
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.masks.enums.maskDomainId import (
    COMPOSE_CONTRIBUTOR_ORDER,
    TERRAIN_MERGE_RANK_HIGH_TO_LOW,
    MaskDomainId,
)
from app.dataModel.terrainMasks import WorldTerrainMasks


class TestTerrainMasks(unittest.TestCase):
    def setUp(self) -> None:
        self.masks = WorldTerrainMasks.canonical_defaults()
        self.terrain = {
            self.masks.default_plains.system_terrain,
            self.masks.default_forests.system_terrain,
            self.masks.default_mountains.system_terrain,
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

    def test_cold_is_plains_not_tundra_terrain(self) -> None:
        """Cold biome stays on climate_zone_id; landcover paints plains (or forest if wet)."""
        tundra = ClimateZone.TUNDRA.to_profile()
        key = resolve_forest_plains(
            base_rainfall=tundra.base_rainfall,
            base_temperature=tundra.base_temperature,
            terrain_set=self.terrain,
            forests=self.masks.default_forests,
            plains=self.masks.default_plains,
        )
        self.assertEqual(key, self.masks.default_plains.system_terrain)
        self.assertNotEqual(key, "tundra")

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

    def test_merge_rank_follows_mask_domain_id(self) -> None:
        order = self.masks.merge_rank_order()
        expected = tuple(
            self.masks.system_terrain_for_domain(d)
            for d in TERRAIN_MERGE_RANK_HIGH_TO_LOW
        )
        self.assertEqual(order, expected)
        self.assertEqual(
            self.masks.system_terrain_for_domain(MaskDomainId.MOUNTAINS),
            self.masks.default_mountains.system_terrain,
        )
        self.assertIsNone(self.masks.system_terrain_for_domain(MaskDomainId.HYDROLOGY))

    def test_default_pipeline_from_compose_order_sot(self) -> None:
        contributors = build_default_contributors()
        self.assertEqual(
            tuple(c.name for c in contributors),
            tuple(cid.value for cid in COMPOSE_CONTRIBUTOR_ORDER),
        )


if __name__ == "__main__":
    unittest.main()
