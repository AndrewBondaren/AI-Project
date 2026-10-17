"""Surface mask domains — forest/plains resolve + WorldTerrainMasks (SM-*)."""

from __future__ import annotations

import json
import unittest

from app.application.worldData.masks.resolveForestPlains import resolve_forest_plains
from app.application.worldData.masks.terrainMerge import may_paint_terrain, terrain_merge_rank
from app.application.worldData.pack.bake.lightGrid.maskDomainRegistry import (
    build_default_contributors,
)
from app.dataModel.climate.enums.climateZone import ClimateZone
from app.dataModel.masks.enums.maskDomainId import (
    COMPOSE_CONTRIBUTOR_ORDER,
    MaskDomainId,
)
from app.dataModel.terrainMasks import WorldTerrainMasks
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrainMasks.hillShape import HillShape


class TestTerrainMasks(unittest.TestCase):
    def setUp(self) -> None:
        self.masks = WorldTerrainMasks.canonical_defaults()
        self.registry = WorldTerrainRegistry.canonical_defaults()
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
                self.registry,
            )
        )
        self.assertFalse(
            may_paint_terrain(
                self.masks.default_roads.system_terrain,
                self.masks.default_mountains.system_terrain,
                self.registry,
            )
        )

    def test_merge_rank_preserves_builtin_order(self) -> None:
        policies = (
            self.masks.default_roads, self.masks.default_ravines, self.masks.default_mountains,
            self.masks.default_forests, self.masks.default_plains,
        )
        ranks = [terrain_merge_rank(policy.system_terrain, self.registry) for policy in policies]
        self.assertEqual(ranks, list(range(len(policies), 0, -1)))

    def test_default_pipeline_from_compose_order_sot(self) -> None:
        contributors = build_default_contributors()
        self.assertEqual(
            tuple(c.name for c in contributors),
            tuple(cid.value for cid in COMPOSE_CONTRIBUTOR_ORDER),
        )

    def test_consumer_owns_hills_not_mask_domain(self) -> None:
        self.assertFalse(hasattr(MaskDomainId, "HILLS"))
        plains = self.masks.default_plains.hills
        forest = self.masks.default_forests.hills
        self.assertEqual(
            (plains.min_spacing, plains.radius, plains.height, plains.shapes),
            (500, 40, 2, ()),
        )
        self.assertEqual(
            (forest.min_spacing, forest.radius, forest.height, forest.shapes),
            (500, 25, 2, ()),
        )
        self.assertEqual(plains.resolved_shapes(), HillShape.catalog())

    def test_world_template_hills_match_pojo(self) -> None:
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "fixtures" / "world_template.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        hills = raw["world"]["terrain_masks"]
        plains = self.masks.default_plains.hills
        forest = self.masks.default_forests.hills
        self.assertEqual(hills["default_plains"]["hills"], plains.model_dump(mode="json"))
        self.assertEqual(hills["default_forests"]["hills"], forest.model_dump(mode="json"))



if __name__ == "__main__":
    unittest.main()
