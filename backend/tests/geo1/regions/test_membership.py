"""Exact spans versus the existing geometry/rasterizer oracle, including topology aliases."""

from dataclasses import replace
from itertools import product
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.application.worldData.generators.terrain.regions.coverageMeasure import RegionCoverageMeasure
from app.application.worldData.generators.terrain.regions.shapeCoverage import coverage_for_shape
from app.application.worldData.masks.regionRasterContext import RegionRasterContext
from app.application.worldData.masks.regionRasterizer import geometry_membership, rasterize_fine
from app.dataModel.spatial.grid.lightGridScale import LightGridScale
from app.dataModel.spatial.regionShape import BboxShape, CorridorShape, EdgeNoise, EllipseShape, PolygonShape
from app.dataModel.terrainMasks.regions import ForestSpec
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from app.dataModel.topology.worldBounds import WorldBounds
from app.dataModel.topology.worldTopology import WorldTopology
from app.ids import seed_root
from tests.geo1.regions.test_coverage import cells


WORLD = SimpleNamespace(world_uid="region-world")
UID = "region-a"


def topology(mode=Mode.WRAPPED):
    return WorldTopology(mode=mode, bounds=WorldBounds(x_min=-4, x_max=7, y_min=-3, y_max=5))


def shapes():
    return (BboxShape(x_min=-7, y_min=-5, x_max=11, y_max=8),
            EllipseShape(cx=5, cy=4, rx=5, ry=4),
            PolygonShape(vertices=((-6, -4), (10, -4), (5, 2), (10, 8), (-6, 8), (-2, 2))),
            CorridorShape(path=((-7, -3), (4, 2), (9, 2), (9, 8)), width=3))


class MembershipTests(TestCase):
    def test_all_shapes_noise_and_topology_modes_match_existing_membership(self):
        for mode, shape, noisy in product(Mode, shapes(), (False, True)):
            with self.subTest(mode=mode, kind=shape.kind, noisy=noisy):
                if noisy:
                    shape = type(shape).model_validate(shape.model_dump() | {"edge_noise": EdgeNoise(amplitude=3, scale=2)})
                topo = topology(mode)
                predicate = geometry_membership(shape, seed_root(WORLD), UID, topo)
                xmin, ymin, xmax, ymax = shape.bbox()
                expected = set()
                for y in range(ymin, ymax + 1):
                    for x in range(xmin, xmax + 1):
                        canonical = topo.canonicalize(x, y)
                        if canonical is not None and predicate((x, y), canonical):
                            expected.add(canonical)
                result = coverage_for_shape(shape, root=seed_root(WORLD), region_uid=UID, topology=topo)
                self.assertEqual(cells(result), expected)
                self.assertEqual(RegionCoverageMeasure.area(result), len(expected))

    def test_discrete_area_is_not_polygon_continuous_area_or_bbox(self):
        shape = PolygonShape(vertices=((0, 0), (4, 0), (0, 4)))
        result = coverage_for_shape(shape, root=seed_root(WORLD), region_uid=UID, topology=topology(Mode.PLANAR))
        self.assertEqual(RegionCoverageMeasure.area(result), 15)
        self.assertNotEqual(RegionCoverageMeasure.area(result), shape.area())
        self.assertNotEqual(RegionCoverageMeasure.area(result), 25)

    def test_geometry_measure_ignores_paint_density_and_preserves_rasterizer(self):
        shape = EllipseShape(cx=2, cy=1, rx=4, ry=3, edge_noise=EdgeNoise(amplitude=2, scale=2))
        topo = topology()
        spec = ForestSpec(name="density region", shape=shape, density=1)
        ctx = RegionRasterContext(region_uid=UID, spec=spec, scale=LightGridScale.from_tile(tile_macro=1, side=1), topology=topo)
        measured = coverage_for_shape(shape, root=seed_root(WORLD), region_uid=UID, topology=topo)
        self.assertEqual(cells(measured), rasterize_fine(shape, WORLD, ctx))
        no_paint = replace(ctx, spec=spec.model_copy(update={"density": 0.0}))
        self.assertEqual(rasterize_fine(shape, WORLD, no_paint), set())
        self.assertGreater(RegionCoverageMeasure.area(measured), 0)

    def test_huge_bbox_width_uses_spans_not_fine_cell_enumeration(self):
        topo = WorldTopology(mode=Mode.PLANAR, bounds=WorldBounds(x_min=0, x_max=10_000_000, y_min=0, y_max=3))
        shape = BboxShape(x_min=0, x_max=10_000_000, y_min=0, y_max=3)
        with patch.object(BboxShape, "contains", side_effect=AssertionError("enumerated bbox fine cells")), \
             patch.object(BboxShape, "area", side_effect=AssertionError("used continuous estimator")):
            result = coverage_for_shape(shape, root=seed_root(WORLD), region_uid=UID, topology=topo)
        self.assertEqual(len(result.spans), 4)
        self.assertEqual(RegionCoverageMeasure.area(result), 40_000_004)

    def test_multiple_unrolled_aliases_do_not_multiply_area(self):
        for mode in (Mode.WRAPPED, Mode.SPHERE):
            topo = topology(mode)
            result = coverage_for_shape(BboxShape(x_min=-40, x_max=40, y_min=-30, y_max=30),
                root=seed_root(WORLD), region_uid=UID, topology=topo)
            self.assertEqual(RegionCoverageMeasure.area(result), topo.bounds.width * topo.bounds.height)
            self.assertEqual(len(result.spans), topo.bounds.height)

    def test_huge_rectangle_aliases_do_not_enumerate_every_unrolled_row(self):
        for mode in (Mode.WRAPPED, Mode.SPHERE):
            topo = topology(mode)
            result = coverage_for_shape(BboxShape(x_min=-100, x_max=100, y_min=-1_000_000_000, y_max=1_000_000_000),
                root=seed_root(WORLD), region_uid=UID, topology=topo)
            self.assertEqual(RegionCoverageMeasure.area(result), topo.bounds.width * topo.bounds.height)
