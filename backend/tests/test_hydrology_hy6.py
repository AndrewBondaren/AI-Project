"""HY-6 matrix A1–C: nearest-segment water side, endpoints, and footprint seam."""

import unittest

from tests.hydrology_fixtures import hydro_topology

from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from tests.hydrology_geometry_helpers import (_land_shore_cells, compute_land_centroid, flood_water_side, flood_water_side_unbounded, water_side_seeds)
from app.application.worldData.generators.hydrology.shore.waterSideFootprint import (
    CoastlineWaterSide,
    water_side_footprint,
)
from tests.hydrology_fixtures import (
    flat_heightmap,
)


class TestWaterSidePerpendicular(unittest.TestCase):
    def setUp(self):
        self.hm = flat_heightmap(0, 10, 0, 6)
        self.topology = hydro_topology(self.hm)

    def flood(self, segments, *, bounded=True):
        flood = flood_water_side if bounded else flood_water_side_unbounded
        return flood(self.hm, rasterize_segments(segments), segments, topology=self.topology)

    def test_a1_east_west_and_b_projection(self):
        segments = [((2, 2), (8, 2))]
        bounded = self.flood(segments)
        unbounded = self.flood(segments, bounded=False)
        self.assertIn((5, 1), bounded)
        self.assertIn((2, 1), bounded)
        self.assertNotIn((0, 1), bounded)
        self.assertNotIn((10, 0), bounded)
        self.assertIn((0, 1), unbounded)
        self.assertIn((10, 0), unbounded)
        for cells in (bounded, unbounded):
            self.assertNotIn((5, 3), cells)
            self.assertNotIn((0, 3), cells)

    def test_a2_north_south(self):
        segments = [((2, 1), (2, 5))]
        for bounded in (True, False):
            with self.subTest(bounded=bounded):
                water = self.flood(segments, bounded=bounded)
                self.assertIn((1, 3), water)
                self.assertNotIn((3, 3), water)
                self.assertEqual(water[(1, 3)], 1)
                self.assertEqual(water[(0, 3)], 2)

    def test_a3_no_endpoint_leak(self):
        segments = [((2, 1), (2, 5))]
        for bounded in (True, False):
            water = self.flood(segments, bounded=bounded)
            self.assertNotIn((2, 0), water)
            self.assertNotIn((3, 0), water)
            self.assertNotIn((2, 6), water)
            self.assertNotIn((3, 6), water)
            self.assertEqual((1, 0) in water, not bounded)
            self.assertEqual((1, 6) in water, not bounded)

    def test_a4_diagonal_dot_wall(self):
        # Land south of the diagonal fixes the matrix's north/east water normal.
        for x in range(11):
            self.hm.surface_z[(x, 6)] = 100
        segments = [((1, 1), (5, 5))]
        for bounded in (True, False):
            water = self.flood(segments, bounded=bounded)
            self.assertIn((3, 2), water)
            self.assertNotIn((2, 3), water)
            self.assertTrue(all(x > y for x, y in water))
            self.assertTrue(set(water).isdisjoint(rasterize_segments(segments)))

    def test_a5_corner_uses_max_dot_and_footprint_is_order_independent(self):
        segments = [((2, 1), (2, 4)), ((2, 4), (6, 4))]
        expected = self.flood(segments, bounded=False)
        self.assertIn((0, 5), expected)
        self.assertIn((1, 6), expected)
        self.assertNotIn((3, 3), expected)
        for order in (segments, list(reversed(segments))):
            geometry = CoastlineWaterSide(rasterize_segments(order), order,
                                         compute_land_centroid(self.hm, topology=self.topology), topology=self.topology)
            self.assertEqual(geometry.at((0, 5)).step, (-1, 0))
            self.assertEqual(geometry.at((1, 6)).step, (0, 1))
            self.assertEqual(set(expected), set(self.flood(order, bounded=False)))

    def test_equal_dot_uses_coast_gy_gx_order(self):
        segments = [((1, 2), (3, 2)), ((5, 2), (7, 2))]
        for order in (segments, list(reversed(segments))):
            geometry = CoastlineWaterSide(rasterize_segments(order), order, (4, 6), topology=self.topology)
            self.assertEqual(geometry.at((4, 1)).coast, (3, 2))
            self.assertTrue(geometry.contains((4, 1), bounded=False))
            self.assertFalse(geometry.contains((4, 1), bounded=True))

    def test_a6_water_outside_bounds_and_empty_input(self):
        for segments in ([((0, 1), (0, 5))], []):
            for bounded in (True, False):
                self.assertEqual(self.flood(segments, bounded=bounded), {})

    def test_c_shore_and_seeds_agree_with_water_normal(self):
        segments = [((2, 1), (2, 5))]
        coast = rasterize_segments(segments)
        centroid = compute_land_centroid(self.hm, topology=self.topology)
        shore = _land_shore_cells(coast, segments, self.hm, centroid, topology=self.topology)
        seeds = water_side_seeds(coast, segments, self.hm, centroid, topology=self.topology)
        self.assertIn((3, 3), shore)
        self.assertNotIn((2, 0), shore)
        self.assertIn((1, 3), seeds)
        self.assertTrue(seeds <= self.flood(segments).keys())
        self.assertTrue(shore.isdisjoint(self.flood(segments, bounded=False)))

    def test_passable_predicate_blocks_flood_without_mutation(self):
        segments = [((4, 1), (4, 5))]
        geometry = CoastlineWaterSide(rasterize_segments(segments), segments, (8, 3), topology=self.topology)
        before = dict(self.hm.surface_z)
        water = water_side_footprint(
            geometry, bounded=False,
            passable=lambda c: c in self.hm.surface_z and c[0] != 2,
        )
        self.assertIn((3, 3), water)
        self.assertFalse(any(x <= 2 for x, _ in water))
        self.assertEqual(self.hm.surface_z, before)
        self.assertEqual(water_side_footprint(geometry, bounded=True,
                                            passable=lambda c: False), {})

    def test_projection_belongs_to_nearest_segment_not_other_branch(self):
        segments = [((2, 1), (2, 4)), ((2, 4), (6, 4))]
        geometry = CoastlineWaterSide(rasterize_segments(segments), segments, (5, 3), topology=self.topology)
        # Nearest vertical segment wins even though horizontal projection is in range.
        self.assertFalse(geometry.contains((3, 0), bounded=False))
        self.assertTrue(geometry.contains((0, 3), bounded=True))
        self.assertFalse(geometry.contains((0, 0), bounded=True))
        self.assertTrue(geometry.contains((0, 0), bounded=False))

    def test_nearest_segment_is_not_nearest_raster_cell(self):
        segments = [((1, 2), (3, 1)), ((1, 5), (0, 0))]
        geometry = CoastlineWaterSide(rasterize_segments(segments), segments, (4, 8), topology=self.topology)
        # (2,3): segment distances squared 9/5 < 49/26, raster distances 2 > 1.
        # The first segment must supply both normal and t despite its farther raster.
        side = geometry.at((2, 3))
        self.assertEqual(side.step, (-1, -1))
        self.assertEqual(side.projection.numerator, 1)
        self.assertEqual(side.projection.denominator, 5)

    def test_degenerate_segment_fallback_and_missing_surface(self):
        segments = [((2, 3), (2, 3))]
        self.assertIn((1, 3), self.flood(segments))
        self.hm.surface_z.clear()
        self.assertEqual(self.flood(segments), {})


if __name__ == "__main__":
    unittest.main()
