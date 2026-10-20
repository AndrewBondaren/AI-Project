"""One membership field sampled at light centers and individual fine cells."""

from dataclasses import replace
from types import SimpleNamespace
import unittest

from app.application.worldData.masks.footprint import LightCellRef
from app.application.worldData.masks.regionRasterContext import ClaimSeed, RegionClaim, RegionRasterContext
from app.application.worldData.masks.regionRasterizer import (
    ClaimOwnersIndex, rasterize_claim_fine, rasterize_claim_light, rasterize_fine, rasterize_light,
)
from app.ids import seed_root
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale, light_cell_center_fine
from app.dataModel.spatial.regionShape import AnchorRadiusShape, BboxShape, EdgeNoise, EllipseShape, PolygonShape
from app.dataModel.terrainMasks.regions import ForestSpec
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode


class RegionRasterizerTests(unittest.TestCase):
    def setUp(self):
        self.world = SimpleNamespace(world_uid="raster-world")
        self.uid = "region-a"
        self.other_uid = "region-b"
        self.bounds = WorldBounds(x_min=0, x_max=3, y_min=0, y_max=2)
        self.scale = LightGridScale.from_tile(tile_macro=8, side=4)
        self.shape = BboxShape(x_min=2, y_min=2, x_max=14, y_max=14)
        self.spec = ForestSpec(name="Test region", shape=self.shape)
        self.ctx = RegionRasterContext(
            region_uid=self.uid, spec=self.spec, scale=self.scale,
            topology=WorldTopology(mode=WorldTopologyMode.PLANAR, bounds=self.bounds),
        )
        self.no_noise = EdgeNoise(amplitude=0, scale=1)

    def with_mode(self, mode):
        return replace(self.ctx, topology=WorldTopology(mode=mode, bounds=self.bounds))

    def index(self, claim, ctx=None):
        ctx = ctx or self.ctx
        return ClaimOwnersIndex(claim, seed_root(self.world), ctx.fine_topology())

    def centers(self, ctx):
        bounds, scale = ctx.topology.bounds, ctx.scale
        return {
            LightCellRef(gx, gy, tx, ty): light_cell_center_fine(gx, gy, tx, ty, scale)
            for gx in range(bounds.x_min, bounds.x_max + 1)
            for gy in range(bounds.y_min, bounds.y_max + 1)
            for tx in range(scale.side) for ty in range(scale.side)
        }

    def assert_same_samples(self, shape, ctx):
        fine = rasterize_fine(shape, self.world, ctx)
        light = rasterize_light(shape, self.world, ctx)
        expected = frozenset(cell for cell, center in self.centers(ctx).items() if center in fine)
        self.assertEqual(light, expected)
        self.assertIsInstance(light, frozenset)
        self.assertIsInstance(fine, set)
        return fine, light

    def test_all_absolute_primitives_use_same_membership_at_both_resolutions(self):
        shapes = (
            self.shape,
            EllipseShape(cx=8, cy=8, rx=7, ry=5),
            PolygonShape(vertices=[(1, 1), (15, 1), (9, 5), (15, 15), (1, 15)]),
        )
        for shape in shapes:
            with self.subTest(shape=shape.kind):
                fine, light = self.assert_same_samples(shape, self.ctx)
                self.assertTrue(fine)
                self.assertTrue(light)
                expected = {(x, y) for x in range(16) for y in range(16) if shape.contains(x, y)}
                self.assertEqual(fine, expected)

    def test_fine_contour_is_not_nearest_carry_from_l0(self):
        shape = EllipseShape(cx=8, cy=8, rx=7, ry=5)
        fine, light = self.assert_same_samples(shape, self.ctx)
        self.assertIn((15, 8), fine)
        self.assertNotIn((15, 9), fine)
        # Same light cell, distinct fine membership at the ellipse boundary.
        self.assertNotIn(LightCellRef(1, 1, 3, 0), light)

    def test_wrapped_shape_crosses_both_axes_and_replays_from_unrolled_image(self):
        ctx = self.with_mode(WorldTopologyMode.WRAPPED)
        shape = BboxShape(x_min=29, x_max=35, y_min=21, y_max=27)
        fine, light = self.assert_same_samples(shape, ctx)
        self.assertIn((0, 0), fine)
        self.assertIn((31, 23), fine)
        self.assertEqual({cell.gx for cell in light}, {0, 3})
        translated = shape.model_copy(update={"x_min": -3, "x_max": 3, "y_min": -3, "y_max": 3})
        self.assertEqual(rasterize_fine(translated, self.world, ctx), fine)
        self.assertEqual(rasterize_light(translated, self.world, ctx), light)

    def test_planar_clips_void_without_moving_shape(self):
        shape = BboxShape(x_min=-3, y_min=-3, x_max=3, y_max=3)
        fine, _ = self.assert_same_samples(shape, self.ctx)
        self.assertEqual(fine, {(x, y) for x in range(4) for y in range(4)})
        outside = BboxShape(x_min=40, x_max=42, y_min=0, y_max=2)
        self.assertEqual(rasterize_fine(outside, self.world, self.ctx), set())
        self.assertEqual(rasterize_light(outside, self.world, self.ctx), frozenset())

    def test_sphere_reflects_light_centers_across_north_and_south_edges(self):
        ctx = self.with_mode(WorldTopologyMode.SPHERE)
        for lo, hi in ((23, 27), (-4, 0)):
            shape = BboxShape(x_min=1, x_max=5, y_min=lo, y_max=hi)
            with self.subTest(y=(lo, hi)):
                fine, light = self.assert_same_samples(shape, ctx)
                self.assertTrue(any(x >= 16 for x, _ in fine))
                self.assertTrue(light)

    def test_negative_macro_origins_and_nondivisible_tile_scale(self):
        bounds = WorldBounds(x_min=-2, x_max=1, y_min=-1, y_max=1)
        ctx = replace(self.ctx, scale=LightGridScale.from_tile(10, 3),
                      topology=WorldTopology(mode=WorldTopologyMode.SPHERE, bounds=bounds))
        shape = BboxShape(x_min=-24, x_max=-5, y_min=18, y_max=23)
        fine, light = self.assert_same_samples(shape, ctx)
        self.assertTrue(fine)
        self.assertTrue(light)
        self.assertTrue(all(0 <= cell.tx < ctx.scale.side and 0 <= cell.ty < ctx.scale.side for cell in light))

    def test_density_uses_canonical_uid_field_and_same_fine_samples(self):
        ctx = self.with_mode(WorldTopologyMode.WRAPPED)
        ctx = replace(ctx, spec=self.spec.model_copy(update={"density": 0.45}))
        fine, _ = self.assert_same_samples(self.shape, ctx)
        self.assertTrue(fine)
        self.assertLess(len(fine), len(rasterize_fine(self.shape, self.world, self.ctx)))
        translated = self.shape.model_copy(update={"x_min": 34, "x_max": 46})
        self.assertEqual(rasterize_fine(translated, self.world, ctx), fine)
        self.assertEqual(rasterize_fine(self.shape, self.world, ctx), fine)
        empty = replace(ctx, spec=self.spec.model_copy(update={"density": 0}))
        self.assertEqual(rasterize_light(self.shape, self.world, empty), frozenset())
        self.assertEqual(rasterize_fine(self.shape, self.world, empty), set())

    def test_edge_noise_is_correlated_deterministic_and_leaves_deep_interior(self):
        scale = LightGridScale.from_tile(16, 8)
        ctx = replace(self.ctx, scale=scale)
        edge = EdgeNoise(amplitude=6, scale=8)
        shape = BboxShape(x_min=4, x_max=55, y_min=4, y_max=43, edge_noise=edge)
        fine, _ = self.assert_same_samples(shape, ctx)
        self.assertEqual(fine, rasterize_fine(shape, self.world, ctx))
        self.assertTrue(all((x, y) in fine for x in range(11, 49) for y in range(11, 37)))
        self.assertTrue(all(shape.contains(x, y) for x, y in fine))
        left_edge = [min(x for x in range(4, 15) if (x, y) in fine) for y in range(12, 36)]
        self.assertGreater(len(set(left_edge)), 1)
        self.assertLessEqual(max(abs(a - b) for a, b in zip(left_edge, left_edge[1:])), 2)
        other_ctx = replace(ctx, region_uid=self.other_uid)
        self.assertNotEqual(fine, rasterize_fine(shape, self.world, other_ctx))

    def test_zero_edge_amplitude_does_not_change_geometry(self):
        shape = self.shape.model_copy(update={"edge_noise": self.no_noise})
        self.assertEqual(rasterize_fine(shape, self.world, self.ctx),
                         rasterize_fine(self.shape, self.world, self.ctx))

    def test_noisy_ellipse_polygon_and_wrapped_image_share_membership(self):
        edge = EdgeNoise(amplitude=3, scale=4)
        ctx = self.with_mode(WorldTopologyMode.WRAPPED)
        shapes = (
            EllipseShape(cx=30, cy=12, rx=6, ry=8, edge_noise=edge),
            PolygonShape(vertices=[(27, 3), (37, 7), (30, 21)], edge_noise=edge),
        )
        for shape in shapes:
            with self.subTest(shape=shape.kind):
                fine, light = self.assert_same_samples(shape, ctx)
                self.assertTrue(fine)
                self.assertTrue(light)
        shifted = self.shape.model_copy(update={"x_min": 34, "x_max": 46, "edge_noise": edge})
        noisy = self.shape.model_copy(update={"edge_noise": edge})
        self.assertEqual(rasterize_fine(noisy, self.world, ctx), rasterize_fine(shifted, self.world, ctx))
        self.assertEqual(rasterize_light(noisy, self.world, ctx), rasterize_light(shifted, self.world, ctx))

    def test_unresolved_anchor_is_an_error_and_shape_is_never_mutated(self):
        anchor = AnchorRadiusShape(anchor_uid="anchor", radius=3)
        for rasterize in (rasterize_fine, rasterize_light):
            with self.assertRaises(ValueError):
                rasterize(anchor, self.world, self.ctx)
        before = self.shape.model_dump()
        rasterize_fine(self.shape, self.world, self.ctx)
        self.assertEqual(self.shape.model_dump(), before)

    def test_missing_world_identity_is_not_replaced_with_fallback_seed(self):
        with self.assertRaises(ValueError):
            rasterize_fine(self.shape, SimpleNamespace(), self.ctx)

    def test_claim_radius_and_tie_use_canonical_seed_order(self):
        left = ClaimSeed((10, 10), self.uid)
        right = ClaimSeed((20, 10), self.other_uid)
        claim = RegionClaim((right, left), max_radius=10, noise=self.no_noise)
        fine = rasterize_claim_fine(self.index(claim), self.world, self.ctx)
        self.assertIn((15, 10), fine)
        self.assertNotIn((16, 10), fine)
        self.assertTrue(all(abs(x - 10) + abs(y - 10) <= claim.max_radius for x, y in fine))
        self.assertEqual(fine, rasterize_claim_fine(self.index(replace(claim, seeds=(left, right))), self.world, self.ctx))

    def test_claim_noise_distinguishes_seeds_and_bends_competition_boundary(self):
        seeds = (ClaimSeed((10, 10), self.uid), ClaimSeed((20, 10), self.other_uid))
        claim = RegionClaim(seeds, max_radius=18, noise=EdgeNoise(amplitude=4, scale=4))
        fine = rasterize_claim_fine(self.index(claim), self.world, self.ctx)
        right_edges = [max(x for x in range(8, 23) if (x, y) in fine) for y in range(4, 17)]
        self.assertGreater(len(set(right_edges)), 1)
        self.assertEqual(fine, rasterize_claim_fine(self.index(claim), self.world, self.ctx))
        other = rasterize_claim_fine(self.index(claim), self.world, replace(self.ctx, region_uid=self.other_uid))
        self.assertFalse(fine & other)

    def test_claim_scope_filters_result_and_never_truncates_competitors(self):
        seeds = (ClaimSeed((4, 9), self.uid), ClaimSeed((14, 9), self.other_uid))
        claim = RegionClaim(seeds, max_radius=12, noise=EdgeNoise(amplitude=3, scale=4))
        full = rasterize_claim_fine(self.index(claim), self.world, self.ctx)
        scope = (0, 0, 9, 23)
        partial = rasterize_claim_fine(self.index(claim), self.world, self.ctx, scope=scope)
        self.assertEqual(partial, {(x, y) for x, y in full if x <= scope[2]})
        full_light = rasterize_claim_light(self.index(claim), self.world, self.ctx)
        self.assertEqual(full_light, frozenset(cell for cell, center in self.centers(self.ctx).items() if center in full))

    def test_claim_uses_wrapped_and_sphere_neighbors_and_planar_void(self):
        claim = RegionClaim((ClaimSeed((0, 10), self.uid),), max_radius=2, noise=self.no_noise)
        planar = rasterize_claim_fine(self.index(claim), self.world, self.ctx)
        wrapped = rasterize_claim_fine(self.index(claim, self.with_mode(WorldTopologyMode.WRAPPED)),
                                       self.world, self.with_mode(WorldTopologyMode.WRAPPED))
        self.assertNotIn((31, 10), planar)
        self.assertIn((31, 10), wrapped)
        sphere_ctx = self.with_mode(WorldTopologyMode.SPHERE)
        polar = replace(claim, seeds=(ClaimSeed((3, 23), self.uid),), max_radius=1)
        self.assertIn((19, 23), rasterize_claim_fine(self.index(polar, sphere_ctx), self.world, sphere_ctx))

    def test_claim_canonical_seed_images_and_density_match_both_grids(self):
        ctx = self.with_mode(WorldTopologyMode.WRAPPED)
        ctx = replace(ctx, spec=self.spec.model_copy(update={"density": 0.6}))
        seed = ClaimSeed((31, 10), self.uid)
        claim = RegionClaim((seed,), max_radius=8, noise=EdgeNoise(amplitude=2, scale=4))
        fine = rasterize_claim_fine(self.index(claim, ctx), self.world, ctx)
        light = rasterize_claim_light(self.index(claim, ctx), self.world, ctx)
        image = replace(claim, seeds=(replace(seed, coord=(-1, 10)),))
        self.assertEqual(fine, rasterize_claim_fine(self.index(image, ctx), self.world, ctx))
        self.assertEqual(light, frozenset(cell for cell, center in self.centers(ctx).items() if center in fine))

    def test_empty_claim_zero_radius_and_invalid_cap(self):
        claim = RegionClaim((), max_radius=0, noise=self.no_noise)
        self.assertEqual(rasterize_claim_fine(self.index(claim), self.world, self.ctx), set())
        seed = ClaimSeed((3, 3), self.uid)
        self.assertEqual(rasterize_claim_fine(self.index(replace(claim, seeds=(seed,))), self.world, self.ctx), {seed.coord})
        with self.assertRaises(ValueError):
            replace(claim, max_radius=-1)


if __name__ == "__main__":
    unittest.main()
