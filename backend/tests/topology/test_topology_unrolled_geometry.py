"""HY-11: geometry in one unrolled frame, canonical writes at world seams."""

import unittest
from fractions import Fraction
from itertools import product

from app.dataModel.spatial.facing import CARDINAL_FACINGS, Facing
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode
from app.dataModel.topology.topologyGeometry import (
    canonical_frame, centroid, dist2, nearest_on_segment, neighbors4_unrolled, unrolled_images,
)
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


class TopologyUnrolledGeometryTests(unittest.TestCase):
    def setUp(self):
        self.bounds = WorldBounds(x_min=-2, x_max=1, y_min=3, y_max=5)
        self.planar, self.wrapped, self.sphere = (
            WorldTopology(mode=mode, bounds=self.bounds) for mode in (
                WorldTopologyMode.PLANAR, WorldTopologyMode.WRAPPED, WorldTopologyMode.SPHERE,
            )
        )
        self.cells = tuple(product(range(-2, 2), range(3, 6)))

    def test_planar_has_one_image_and_ordinary_metric(self):
        images = unrolled_images(self.planar, (-2, 3), anchor=(100, 100))
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].coord, (-2, 3))
        self.assertFalse(images[0].invert_dy)
        self.assertEqual(dist2(self.planar, (-2, 3), (1, 5)), 13)

    def test_wrapped_images_cover_both_periods_and_canonicalize_back(self):
        images = unrolled_images(self.wrapped, (-2, 3))
        self.assertEqual({image.coord for image in images},
                         set(product((-6, -2, 2), (0, 3, 6))))
        self.assertTrue(all(not image.invert_dy for image in images))
        self.assertTrue(all(self.wrapped.canonicalize(*image.coord) == (-2, 3)
                            for image in images))

    def test_wrapped_distance_crosses_x_y_and_corner_seams(self):
        self.assertEqual(dist2(self.wrapped, (-2, 4), (1, 4)), 1)
        self.assertEqual(dist2(self.wrapped, (0, 3), (0, 5)), 1)
        self.assertEqual(dist2(self.wrapped, (-2, 3), (1, 5)), 2)
        self.assertLess(dist2(self.wrapped, (-2, 3), (1, 5)),
                        dist2(self.planar, (-2, 3), (1, 5)))

    def test_sphere_fold_images_have_half_turn_and_reflected_orientation(self):
        for cell, expected in (((0, 5), (-2, 6)), ((0, 3), (-2, 2))):
            images = unrolled_images(self.sphere, cell)
            fold = next(image for image in images if image.coord == expected)
            self.assertTrue(fold.invert_dy)
            self.assertTrue(all(self.sphere.canonicalize(*image.coord) == cell
                                for image in images))
        self.assertEqual(dist2(self.sphere, (-2, 5), (0, 5)), 1)
        self.assertEqual(dist2(self.sphere, (-2, 3), (0, 3)), 1)
        # A sphere y-edge is not the torus's opposite row.
        self.assertEqual(dist2(self.sphere, (-2, 3), (-2, 5)), 4)

    def test_distances_match_exhaustive_canonical_image_oracle(self):
        for topology in (self.wrapped, self.sphere):
            # Independently enumerate lifts through the existing canonical map.
            lifts = {cell: [] for cell in self.cells}
            for raw in product(range(-10, 10), range(-6, 15)):
                lifts[topology.canonicalize(*raw)].append(raw)
            for p, q in product(self.cells, repeat=2):
                expected = min((p[0] - x) ** 2 + (p[1] - y) ** 2 for x, y in lifts[q])
                with self.subTest(mode=topology.mode, p=p, q=q):
                    self.assertEqual(dist2(topology, p, q), expected)
                    self.assertEqual(dist2(topology, p, q), dist2(topology, q, p))

    def test_unrolled_queries_and_anchors_can_be_many_periods_away(self):
        for topology in (self.wrapped, self.sphere):
            canonical = (-2, 4)
            anchor = (398, 604)  # 100 x-periods, 100 sphere y-periods.
            image = unrolled_images(topology, canonical, anchor=anchor)[0]
            self.assertEqual(image.coord, anchor)
            self.assertEqual(dist2(topology, anchor, canonical), 0)
            self.assertEqual(dist2(topology, canonical, anchor), 0)

    def test_canonical_frame_preserves_long_paths_instead_of_wrapping_each_vertex(self):
        points = ((-6, 1), (5, 9), (4, -2))
        moved = canonical_frame(self.wrapped, points, anchor=points[0])
        self.assertEqual(moved, ((-2, 4), (9, 12), (8, 1)))
        for original, transformed in zip(points, moved, strict=True):
            self.assertEqual(self.wrapped.canonicalize(*original),
                             self.wrapped.canonicalize(*transformed))

    def test_canonical_frame_reflects_all_sphere_vertices_together(self):
        points = ((0, 6), (1, 7), (2, 8))
        moved = canonical_frame(self.sphere, points, anchor=points[0])
        self.assertEqual(moved, ((-2, 5), (-1, 4), (0, 3)))
        for original, transformed in zip(points, moved, strict=True):
            self.assertEqual(self.sphere.canonicalize(*original),
                             self.sphere.canonicalize(*transformed))

    def test_planar_frame_keeps_void_anchor_for_output_clipping(self):
        points = ((-4, 4), (0, 4))
        self.assertEqual(canonical_frame(self.planar, points, anchor=points[0]), points)

    def test_integer_segment_distance_and_unclamped_projection_are_exact(self):
        result = nearest_on_segment(self.planar, (2, 3), (1, 2), (3, 1))
        self.assertEqual(result.distance2, Fraction(9, 5))
        self.assertEqual(result.projection, Fraction(1, 5))
        self.assertEqual(result.nearest, (Fraction(7, 5), Fraction(9, 5)))
        self.assertEqual(result.image.coord, (2, 3))
        before = nearest_on_segment(self.planar, (0, 1), (2, 2), (8, 2))
        after = nearest_on_segment(self.planar, (10, 1), (2, 2), (8, 2))
        self.assertEqual(before.projection, Fraction(-1, 3))
        self.assertEqual(after.projection, Fraction(4, 3))
        self.assertEqual(before.distance2, 5)
        self.assertEqual(after.distance2, 5)

    def test_wrapped_segment_query_and_nearest_point_share_unrolled_frame(self):
        result = nearest_on_segment(self.wrapped, (1, 4), (-2, 3), (-2, 5))
        self.assertEqual(result.distance2, 1)
        self.assertEqual(result.projection, Fraction(1, 2))
        self.assertEqual(result.image.coord, (-3, 4))
        self.assertEqual(result.nearest, (-2, 4))
        # A seam-crossing segment is supplied unrolled, without a long chord.
        result = nearest_on_segment(self.wrapped, (-2, 4), (1, 3), (3, 5))
        self.assertEqual(result.distance2, 0)
        self.assertEqual(result.projection, Fraction(1, 2))
        self.assertEqual(result.image.coord, (2, 4))

    def test_sphere_segment_projection_retains_fold_frame(self):
        for y, image_y in ((5, 6), (3, 2)):
            result = nearest_on_segment(self.sphere, (0, y), (-2, y), (-2, 4))
            self.assertEqual(result.distance2, 1)
            self.assertEqual(result.projection, -1)
            self.assertEqual(result.image.coord, (-2, image_y))
            self.assertTrue(result.image.invert_dy)
            self.assertEqual(result.nearest, (-2, y))

    def test_long_segment_preserves_extent_and_considers_multiple_periods(self):
        a, b, p = (-2, 3), (38, 23), (-2, 4)
        result = nearest_on_segment(self.wrapped, p, a, b)
        self.assertEqual(result.distance2, 0)
        self.assertTrue(0 <= result.projection <= 1)
        self.assertEqual(self.wrapped.canonicalize(*result.image.coord), p)
        # Planar long segments are also preserved, never shortened by bounds.
        self.assertEqual(nearest_on_segment(self.planar, (18, 13), a, b).projection,
                         Fraction(1, 2))

    def test_point_segment_has_zero_projection_and_topological_distance(self):
        for topology in (self.planar, self.wrapped, self.sphere):
            result = nearest_on_segment(topology, (1, 5), (-2, 3), (-2, 3))
            self.assertEqual(result.projection, 0)
            self.assertEqual(result.nearest, (-2, 3))
            self.assertEqual(result.distance2, dist2(topology, (1, 5), (-2, 3)))

    def test_segment_minimum_matches_exhaustive_canonical_lifts(self):
        segments = (((-2, 3), (1, 5)), ((-2, 5), (-2, 4)),
                    ((1, 3), (3, 5)), ((-2, 3), (-2, 3)))
        for topology in (self.wrapped, self.sphere):
            lifts = {cell: [] for cell in self.cells}
            for raw in product(range(-10, 11), range(-6, 15)):
                lifts[topology.canonicalize(*raw)].append(raw)
            for p, (a, b) in product(self.cells, segments):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length2 = dx * dx + dy * dy
                distances = []
                for x, y in lifts[p]:
                    t = Fraction((x - a[0]) * dx + (y - a[1]) * dy, length2) if length2 else 0
                    clamped = min(1, max(0, t))
                    distances.append((x - a[0] - clamped * dx) ** 2
                                     + (y - a[1] - clamped * dy) ** 2)
                with self.subTest(mode=topology.mode, p=p, segment=(a, b)):
                    self.assertEqual(nearest_on_segment(topology, p, a, b).distance2,
                                     min(distances))

    def test_image_orientation_agrees_with_canonical_north_or_south_step(self):
        for cell in self.cells:
            for image in unrolled_images(self.sphere, cell):
                x, y = image.coord
                facing = Facing.SOUTH if image.invert_dy else Facing.NORTH
                self.assertEqual(self.sphere.canonicalize(x, y + 1),
                                 self.sphere.neighbor(*cell, facing).coord)

    def test_centroid_unwraps_seam_cells_before_weighting(self):
        cells = [(-2, 4), (1, 4)]
        self.assertEqual(centroid(self.wrapped, cells, [1, 3], (-2, 4)), (-2.75, 4))
        self.assertEqual(centroid(self.planar, cells, [1, 3], (-2, 4)), (0.25, 4))
        self.assertEqual(centroid(self.wrapped, reversed(cells), [3, 1], (-2, 4)), (-2.75, 4))
        self.assertEqual(centroid(self.wrapped, cells, [1, 3], (398, 604)), (397.25, 604))

    def test_sphere_centroid_stays_in_anchor_frame_across_both_folds(self):
        for y, expected in ((5, 5.5), (3, 2.5)):
            self.assertEqual(centroid(self.sphere, [(-2, y), (0, y)], [1, 1], (-2, y)),
                             (-2, expected))

    def test_centroid_rejects_undefined_mean_and_mismatched_weights(self):
        for cells, weights in (([], []), ([(0, 4)], [0]), ([(0, 4)], [-1]),
                               ([(0, 4)], [float("nan")]), ([(0, 4)], [float("inf")]),
                               ([(0, 4)], []), ([], [1])):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                centroid(self.wrapped, cells, weights, (0, 4))
        self.assertEqual(centroid(self.wrapped, [(0, 4), (1, 4)], [0, 1], (0, 4)), (1, 4))

    def test_ties_are_deterministic(self):
        self.assertEqual(unrolled_images(self.wrapped, (0, 4), anchor=(-2, 4))[0].coord,
                         (-4, 4))
        result = nearest_on_segment(self.wrapped, (0, 4), (-2, 3), (-2, 5))
        self.assertEqual(result.image.coord, (-4, 4))

    def test_projection_policy_only_breaks_equal_distance_image_ties(self):
        p, a, b = (0, 5), (-2, 5), (-1, 5)
        result = nearest_on_segment(self.sphere, p, a, b,
                                    tie_breaker=lambda result: -result.image.coord[1])
        self.assertEqual(result.distance2, 1)
        self.assertEqual(result.image.coord, (-2, 6))
        self.assertTrue(result.image.invert_dy)
        # A policy that prefers a far image still cannot override the metric.
        result = nearest_on_segment(self.wrapped, (-2, 4), (-2, 3), (-2, 5),
                                    tie_breaker=lambda result: -result.image.coord[0])
        self.assertEqual(result.distance2, 0)
        self.assertEqual(result.image.coord, (-2, 4))

    def test_unrolled_neighbors_canonicalize_to_domain_lookup_or_planar_void(self):
        for topology in (self.planar, self.wrapped, self.sphere):
            for cell in self.cells:
                canonical = {topology.canonicalize(*raw) for raw in neighbors4_unrolled(cell)}
                expected = {result.coord if result else None for result in (
                    topology.neighbor(*cell, facing) for facing in CARDINAL_FACINGS
                )}
                self.assertEqual(canonical, expected)
        self.assertIn((-3, 4), neighbors4_unrolled((-2, 4)))
        self.assertIsNone(self.planar.canonicalize(-3, 4))


if __name__ == "__main__":
    unittest.main()
