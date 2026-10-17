"""One precedence contract for future L0/L2 callers; no paint wiring yet."""

import unittest
from dataclasses import replace
from functools import cmp_to_key, partial
from itertools import permutations
from unittest.mock import Mock

from app.application.worldData.masks.regionPrecedence import (
    RegionCandidate, compare_region_candidates,
)
from app.application.worldData.masks.terrainMerge import terrain_merge_rank
from app.dataModel.registryKey import RegistryKey
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape, EllipseShape, PolygonShape
from app.dataModel.terrain.worldTerrainRegistry import WorldTerrainRegistry
from app.dataModel.terrain.terrainRegistryEntry import TerrainRegistryEntry
from app.dataModel.terrainMasks.regions import ForestSpec

LOG = "app.application.worldData.masks.regionPrecedence"


class RegionPrecedenceTests(unittest.TestCase):
    def setUp(self):
        self.uid_first = "a"
        self.uid_last = "z"
        self.forest_key = WorldTerrainRegistry.forest_terrain_key()
        self.plains_key = WorldTerrainRegistry.plains_terrain_key()
        self.farmland_key = WorldTerrainRegistry.farmland_terrain_key()
        self.steppe_key = "steppe"
        self.registry = WorldTerrainRegistry.canonical_defaults()
        farmland_rank = self.registry.entry_for(self.farmland_key).merge_rank
        steppe = TerrainRegistryEntry(system_terrain=self.steppe_key, terrain_category="solid",
                                     merge_rank=farmland_rank)
        self.registry = WorldTerrainRegistry(self.registry.root + [steppe])
        self.rank = partial(terrain_merge_rank, registry=self.registry)
        self.compare = partial(compare_region_candidates, merge_rank=self.rank)

    def candidate(self, uid, *, specificity=None, side=10, current_type=None, shape=None):
        spec = ForestSpec(
            name=uid,
            shape=shape if shape is not None else BboxShape(x_min=0, y_min=0, x_max=side, y_max=side),
            placement_specificity=specificity,
        )
        return RegionCandidate(
            current_type=RegistryKey[WorldTerrainRegistry](
                current_type if current_type is not None else self.forest_key,
            ),
            spec=spec,
            region_uid=uid,
        )

    def assert_precedes(self, winner, loser):
        self.assertLess(self.compare(winner, loser), 0)
        self.assertGreater(self.compare(loser, winner), 0)

    def test_current_type_rank_beats_specificity_area_and_uid(self):
        forest = self.candidate(self.uid_last, side=1)
        plains = self.candidate(self.uid_first, side=100, specificity=100,
                                current_type=self.plains_key)
        # Both have forest declarations: rank must use current_type, not entry_type.
        with self.assertNoLogs(LOG, level="WARNING"):
            self.assert_precedes(forest, plains)

    def test_specificity_beats_area(self):
        self.assert_precedes(self.candidate(self.uid_last, specificity=2, side=1),
                             self.candidate(self.uid_first, specificity=1, side=100))

    def test_none_loses_to_explicit_zero(self):
        self.assert_precedes(self.candidate(self.uid_last, specificity=0, side=1),
                             self.candidate(self.uid_first, specificity=None, side=100))

    def test_equal_specificity_prefers_larger_area(self):
        for specificity in (None, 0, 3):
            with self.subTest(specificity=specificity):
                self.assert_precedes(self.candidate(self.uid_last, specificity=specificity, side=20),
                                     self.candidate(self.uid_first, specificity=specificity, side=10))

    def test_area_is_primitive_area_not_bbox_or_noise(self):
        vertices = [(0, 0), (10, 0), (0, 10)]
        triangle = self.candidate(self.uid_first, shape=PolygonShape(vertices=vertices))
        square = self.candidate(self.uid_last, side=8)  # bbox 64 < triangle bbox 100, area 64 > 50
        self.assert_precedes(square, triangle)
        noisy = replace(triangle, spec=triangle.spec.model_copy(update={
            "shape": PolygonShape(vertices=vertices,
                                  edge_noise={"amplitude": 1000, "scale": 10}),
        }))
        self.assertEqual(self.compare(triangle, noisy), 0)
        self.assert_precedes(square, noisy)

    def test_anchor_area_does_not_require_anchor_resolution(self):
        anchor = self.candidate(self.uid_last, shape=AnchorRadiusShape(anchor_uid="anchor", radius=10))
        ellipse = self.candidate(self.uid_first, shape=EllipseShape(cx=100, cy=200, rx=5, ry=5))
        self.assert_precedes(anchor, ellipse)

    def test_complete_tie_uses_ascending_uid_and_same_candidate_compares_equal(self):
        first = self.candidate(self.uid_first)
        self.assert_precedes(first, self.candidate(self.uid_last))
        self.assertEqual(self.compare(first, first), 0)

    def test_all_permutations_produce_same_full_order_without_mutation(self):
        uid_unspecified = self.uid_first
        uid_zero = "b"
        uid_small = "c"
        uid_large_first = "d"
        uid_large_last = "e"
        candidates = (
            self.candidate(uid_unspecified, specificity=None, side=100),
            self.candidate(uid_zero, specificity=0, side=100),
            self.candidate(uid_small, specificity=1, side=10),
            self.candidate(uid_large_first, specificity=1, side=20),
            self.candidate(uid_large_last, specificity=1, side=20),
        )
        expected_order = [uid_large_first, uid_large_last, uid_small, uid_zero, uid_unspecified]
        before = tuple(c.spec.model_dump(mode="json") for c in candidates)
        sort_key = cmp_to_key(self.compare)
        for ordering in permutations(candidates):
            result = sorted(ordering, key=sort_key)
            self.assertEqual([c.region_uid for c in result], expected_order)
        self.assertEqual(tuple(c.spec.model_dump(mode="json") for c in candidates), before)

    def test_equal_rank_different_keys_warn_with_same_winner_in_either_order(self):
        # Two explicitly registered keys have the same authored rank.
        farmland = self.candidate(self.uid_last, current_type=self.farmland_key)
        steppe = self.candidate(self.uid_first, current_type=self.steppe_key)
        winner_message = f"winner_uid={steppe.region_uid} winner_type={steppe.current_type}"
        loser_message = f"loser_uid={farmland.region_uid} loser_type={farmland.current_type}"
        for left, right in ((farmland, steppe), (steppe, farmland)):
            with self.subTest(left=left.region_uid), self.assertLogs(LOG, level="WARNING") as caught:
                self.assertEqual(self.compare(left, right), 1 if left is farmland else -1)
            self.assertEqual(len(caught.records), 1)
            message = caught.records[0].getMessage()
            self.assertIn("landcover | equal_rank_resolved | WarningError", message)
            self.assertIn(winner_message, message)
            self.assertIn(loser_message, message)

    def test_equal_rank_different_keys_warn_when_specificity_or_area_decides(self):
        # Inject the rank source rather than duplicating a terrain rank table.
        forest_rank = self.rank(self.forest_key)
        lookup = lambda key: forest_rank
        plains_key = RegistryKey[WorldTerrainRegistry](self.plains_key)
        compare = partial(compare_region_candidates, merge_rank=lookup)
        for winner, loser in (
            (self.candidate(self.uid_last, specificity=0, side=1), self.candidate(self.uid_first, side=100)),
            (self.candidate(self.uid_last, side=20), self.candidate(self.uid_first, side=10)),
        ):
            loser = replace(loser, current_type=plains_key)
            with self.subTest(winner=winner), self.assertLogs(LOG, level="WARNING") as caught:
                self.assertLess(compare(winner, loser), 0)
            self.assertIn(f"winner_uid={winner.region_uid}", caught.records[0].getMessage())

    def test_same_key_equal_rank_does_not_warn(self):
        with self.assertNoLogs(LOG, level="WARNING"):
            self.assert_precedes(self.candidate(self.uid_first), self.candidate(self.uid_last))

    def test_rank_lookup_is_injected_and_can_reverse_existing_order(self):
        forest = self.candidate(self.uid_last)
        plains = self.candidate(self.uid_first, current_type=self.plains_key)
        # A future registry lookup can change the rank source with no comparator edit.
        lookup = Mock(side_effect=lambda key: -self.rank(key))
        self.assertGreater(compare_region_candidates(forest, plains, merge_rank=lookup), 0)
        self.assertEqual([call.args[0] for call in lookup.call_args_list],
                         [forest.current_type, plains.current_type])


if __name__ == "__main__":
    unittest.main()
