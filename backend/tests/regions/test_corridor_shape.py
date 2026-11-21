"""Shared CORRIDOR geometry and fine/light membership through world seams."""

from math import pi
from types import SimpleNamespace
import unittest

from pydantic import TypeAdapter, ValidationError

from app.application.worldData.masks.regionRasterContext import RegionRasterContext
from app.application.worldData.masks.regionRasterNoise import boundary_depth
from app.application.worldData.masks.regionRasterizer import rasterize_fine, rasterize_light
from app.application.worldData.pack.bake.lightGrid.coords import LightGridScale, light_cell_center_fine
from app.dataModel.spatial.regionShape import CorridorShape, EdgeNoise, RegionShape
from app.dataModel.terrainMasks.regions import ForestSpec
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology


class CorridorShapeTests(unittest.TestCase):
    def test_discriminator_roundtrip_and_validation(self):
        adapter = TypeAdapter(RegionShape)
        entry = adapter.validate_python({"kind": "corridor", "path": [[0, 0], [4, 0]], "width": 2})
        self.assertIsInstance(entry, CorridorShape)
        self.assertEqual(adapter.validate_json(adapter.dump_json(entry)), entry)
        for path, width in (([(0, 0)], 2), ([(0, 0), (0, 0)], 2), ([(0, 0), (4, 0)], 0)):
            with self.subTest(path=path, width=width), self.assertRaises(ValidationError):
                CorridorShape(path=path, width=width)

    def test_round_caps_inclusive_distance_and_bbox(self):
        shape = CorridorShape(path=[(0, 0), (4, 0)], width=2)
        self.assertEqual(shape.bbox(), (-1, -1, 5, 1))
        for point in ((-1, 0), (5, 0), (2, 1), (2, -1)):
            self.assertTrue(shape.contains(*point))
        self.assertFalse(shape.contains(5, 1))
        self.assertEqual(boundary_depth(shape, 2, 0), 1)
        self.assertEqual(boundary_depth(shape, 2, 1), 0)

    def test_area_is_geometric_and_does_not_count_retraced_segments_twice(self):
        for path in ([(0, 0), (4, 0)], [(0, 0), (2, 0), (4, 0)],
                     [(0, 0), (4, 0), (0, 0)], [(0, 0), (4, 0), (0, 0), (4, 0)]):
            with self.subTest(path=path):
                self.assertAlmostEqual(CorridorShape(path=path, width=2).area(), 8 + pi)
        bend = CorridorShape(path=[(0, 0), (4, 0), (4, 4)], width=2)
        self.assertAlmostEqual(bend.area(), 15 + 5 * pi / 4)
        reverse = CorridorShape(path=list(reversed(bend.path)), width=2)
        self.assertAlmostEqual(reverse.area(), bend.area())

    def test_area_handles_crossings_and_large_translations(self):
        shape = CorridorShape(path=[(0, 0), (6, 6), (0, 6), (6, 0)], width=3)
        self.assertGreater(shape.area(), 0)
        self.assertLess(shape.area(), sum(CorridorShape(path=[a, b], width=3).area()
                                        for a, b in zip(shape.path, shape.path[1:])))
        moved = CorridorShape(path=[(x + 1000000, y - 2000000) for x, y in shape.path], width=3)
        self.assertAlmostEqual(moved.area(), shape.area())
        self.assertAlmostEqual(CorridorShape(path=list(reversed(shape.path)), width=3).area(), shape.area())
        resized = shape.model_copy(update={"path": [(0, 0), (4, 0)], "width": 2})
        self.assertAlmostEqual(resized.area(), 8 + pi)

    def context(self, mode):
        shape = CorridorShape(path=[(14, 4), (18, 4)], width=2)
        return RegionRasterContext(region_uid="corridor-a", spec=ForestSpec(name="Corridor", shape=shape),
            scale=LightGridScale.from_tile(tile_macro=8, side=4),
            topology=WorldTopology(mode=mode, bounds=WorldBounds(x_min=0, x_max=1, y_min=0, y_max=1)))

    def test_planar_wrapped_and_sphere_membership_at_same_light_samples(self):
        world = SimpleNamespace(world_uid="corridor-world")
        for mode in Mode:
            ctx = self.context(mode)
            shape = ctx.spec.shape
            if mode is Mode.SPHERE:
                shape = CorridorShape(path=[(2, 14), (2, 18)], width=2)
            with self.subTest(mode=mode):
                fine = rasterize_fine(shape, world, ctx)
                self.assertTrue(fine)
                if mode is Mode.WRAPPED:
                    self.assertIn((0, 4), fine)
                if mode is Mode.SPHERE:
                    self.assertIn((10, 15), fine)
                centers = {light_cell_center_fine(gx, gy, tx, ty, ctx.scale)
                           for gx in range(2) for gy in range(2) for tx in range(4) for ty in range(4)}
                light = rasterize_light(shape, world, ctx)
                self.assertEqual({light_cell_center_fine(c.gx, c.gy, c.tx, c.ty, ctx.scale) for c in light}, fine & centers)
                noisy = shape.model_copy(update={"edge_noise": EdgeNoise(amplitude=1, scale=3)})
                self.assertLessEqual(rasterize_fine(noisy, world, ctx), fine)
                self.assertEqual(rasterize_fine(noisy, world, ctx), rasterize_fine(noisy, world, ctx))


if __name__ == "__main__":
    unittest.main()
