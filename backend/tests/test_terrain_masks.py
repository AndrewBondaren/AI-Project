"""Surface mask domains РІР‚вЂќ forest/plains resolve + WorldTerrainMasks (SM-*)."""

from __future__ import annotations

import json
import unittest

from app.application.worldData.generators.terrain.terrainZ import surface_biome_terrain
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
            self.masks.default_landcover.fallback_terrain,
            self.masks.default_landcover.terrain_policy(WorldTerrainRegistry.forest_terrain_key()).system_terrain,
            self.masks.default_mountains.system_terrain,
        }

    def test_defaults_enabled(self) -> None:
        self.assertTrue(self.masks.enabled)
        self.assertTrue(self.masks.category_enabled(self.masks.default_mountains))

    def test_temperate_wet_is_forest_not_mountain(self) -> None:
        temperate = ClimateZone.TEMPERATE.to_profile()
        key = surface_biome_terrain(
            system_climate_zone=temperate.system_climate,
            terrain_set=self.terrain,
            masks=self.masks,
        )
        self.assertEqual(key, self.masks.default_landcover.terrain_policy(WorldTerrainRegistry.forest_terrain_key()).system_terrain)

    def test_arid_is_plains(self) -> None:
        arid = ClimateZone.ARID.to_profile()
        key = surface_biome_terrain(
            system_climate_zone=arid.system_climate,
            terrain_set=self.terrain,
            masks=self.masks,
        )
        self.assertEqual(key, self.masks.default_landcover.fallback_terrain)

    def test_cold_is_plains_not_tundra_terrain(self) -> None:
        """Cold biome stays on climate_zone_id; landcover paints plains (or forest if wet)."""
        tundra = ClimateZone.TUNDRA.to_profile()
        key = surface_biome_terrain(
            system_climate_zone=tundra.system_climate,
            terrain_set=self.terrain,
            masks=self.masks,
        )
        self.assertEqual(key, self.masks.default_landcover.fallback_terrain)
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
            self.masks.default_landcover.terrain_policy(WorldTerrainRegistry.forest_terrain_key()), self.masks.default_landcover.terrain_policy(WorldTerrainRegistry.plains_terrain_key()),
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
        plains = self.masks.default_landcover.hills_for(WorldTerrainRegistry.plains_terrain_key())
        forest = self.masks.default_landcover.hills_for(WorldTerrainRegistry.forest_terrain_key())
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
        policies = raw["world"]["terrain_masks"]["default_landcover"]["terrain_policies"]
        plains = self.masks.default_landcover.hills_for(WorldTerrainRegistry.plains_terrain_key())
        forest = self.masks.default_landcover.hills_for(WorldTerrainRegistry.forest_terrain_key())
        self.assertEqual(policies["plains"]["hills"], plains.model_dump(mode="json"))
        self.assertEqual(policies["forest"]["hills"], forest.model_dump(mode="json"))



if __name__ == "__main__":
    unittest.main()
