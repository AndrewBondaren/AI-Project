"""HY-11 declared flood: world seams, canonical passability and unrolled normals."""

import unittest

from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import build_hydrology_master_input
from tests.hydrology_geometry_helpers import (compute_land_centroid, flood_water_side, flood_water_side_unbounded)
from app.application.worldData.generators.hydrology.shore.waterSideFootprint import (
    CoastlineWaterSide, water_side_footprint,
)
from app.application.worldData.generators.hydrology.types import (
    HydrologyScope,
)
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.hydrology_fixtures import (
    coastline_world,
    flat_heightmap,
    hydro_topology,
    waypoint,
    carve_then_fill,
)


class DeclaredTopologyFloodTests(unittest.TestCase):

    def setUp(self):
        self.hm = flat_heightmap(-2, 2, -2, 2)
        self.topology = hydro_topology(self.hm, Mode.WRAPPED)
        self.segments = [((-2, -1), (-2, 1))]

    def geometry(self, segments=None, centroid=(0, 0)):
        segments = self.segments if segments is None else segments
        return CoastlineWaterSide(rasterize_segments(segments), segments, centroid,
                                  topology=self.topology)


    def test_wrapped_west_coast_flood_reaches_east_with_canonical_distances(self):
        water = flood_water_side(self.hm, rasterize_segments(self.segments), self.segments,
                                 topology=self.topology)
        self.assertEqual(water, {(x, y): 3 - x for x in (1, 2) for y in (-1, 0, 1)})
        self.assertEqual(self.hm.surface_z, flat_heightmap(-2, 2, -2, 2).surface_z)
        self.assertLessEqual(len(water), len(self.hm.surface_z))


    def test_passable_receives_canonical_cells_and_blocks_seam_flood(self):
        seen = []

        def passable(cell):
            seen.append(cell)
            self.assertTrue(self.topology.bounds.contains(*cell))
            return cell in self.hm.surface_z and cell[0] != 1

        before = dict(self.hm.surface_z)
        water = water_side_footprint(self.geometry(), bounded=True, passable=passable)
        self.assertEqual(water, {(2, y): 1 for y in (-1, 0, 1)})
        self.assertTrue(seen)
        self.assertEqual(self.hm.surface_z, before)
        self.assertEqual(water_side_footprint(self.geometry(), bounded=True,
                                             passable=lambda cell: False), {})

    def test_bounded_and_unbounded_keep_endpoint_rules_through_wrapped_seam(self):
        coast = rasterize_segments(self.segments)
        bounded = flood_water_side(self.hm, coast, self.segments, topology=self.topology)
        unbounded = flood_water_side_unbounded(self.hm, coast, self.segments, topology=self.topology)
        self.assertNotIn((2, 2), bounded)
        self.assertIn((2, 2), unbounded)
        self.assertNotIn((-1, 2), unbounded)
        self.assertTrue(set(bounded) <= unbounded.keys())


    def test_unrolled_segment_and_its_translated_image_have_same_canonical_footprint(self):
        first = water_side_footprint(self.geometry(), bounded=True,
                                     passable=lambda cell: cell in self.hm.surface_z)
        translated = [((a[0] + 15, a[1] - 10), (b[0] + 15, b[1] - 10))
                      for a, b in self.segments]
        second = water_side_footprint(self.geometry(translated), bounded=True,
                                      passable=lambda cell: cell in self.hm.surface_z)
        self.assertEqual(first, second)

    def test_centroid_unwraps_weighted_land_and_is_input_order_independent(self):
        self.hm.surface_z.clear()
        self.hm.surface_z.update({(-2, 0): 1, (2, 0): 3})
        center = compute_land_centroid(self.hm, topology=self.topology, anchor=(-2, 0))
        self.assertEqual(center, (-2.75, 0.0))
        reversed_items = list(reversed(tuple(self.hm.surface_z.items())))
        self.hm.surface_z.clear()
        self.hm.surface_z.update(reversed_items)
        self.assertEqual(compute_land_centroid(self.hm, topology=self.topology, anchor=(-2, 0)), center)
        geometry = self.geometry(centroid=center)
        self.assertEqual(geometry.at((2, 0)).point, (-3, 0))
        self.assertLess(geometry.at((2, 0)).dot, 0)  # Weighted land lies west of this coastline.


class SphereDeclaredFloodTests(unittest.TestCase):
    def test_north_and_south_fold_shift_x_and_continue_inverted_y(self):
        for y, inward, raw_seed_y, next_y in ((4, 2, 5, 3), (0, 2, -1, 1)):
            with self.subTest(y=y):
                hm = flat_heightmap(0, 5, 0, 4)
                topology = hydro_topology(hm, Mode.SPHERE)
                segments = [((0, y), (1, y))]
                coast = rasterize_segments(segments)
                geometry = CoastlineWaterSide(coast, segments, (0.5, inward), topology=topology)
                water = water_side_footprint(geometry, bounded=True,
                                             passable=lambda cell: cell in hm.surface_z)
                self.assertEqual(water[(3, y)], 1)
                self.assertEqual(water[(4, y)], 1)
                self.assertEqual(water[(3, next_y)], 2)
                self.assertIn((0, raw_seed_y), geometry.seeds(lambda cell: cell in hm.surface_z))
                self.assertNotIn((0, next_y), water)
                self.assertNotIn((0, 4 - y), water)
                self.assertTrue(all(topology.bounds.contains(*cell) for cell in water))
                self.assertLessEqual(len(water), len(hm.surface_z))


    def test_equal_distance_fold_water_image_is_not_suppressed_by_tangent_image(self):
        hm = flat_heightmap(0, 3, 0, 4)
        topology = hydro_topology(hm, Mode.SPHERE)
        segments = [((0, 4), (1, 4))]
        geometry = CoastlineWaterSide(rasterize_segments(segments), segments, (0.5, 2),
                                      topology=topology)
        water = water_side_footprint(geometry, bounded=True,
                                     passable=lambda cell: cell in hm.surface_z)
        self.assertEqual(water, {(2, 4): 1, (3, 4): 1})
        self.assertEqual(geometry.at((2, 4)).point, (0, 5))
        self.assertGreater(geometry.at((2, 4)).dot, 0)


class TopologyConsumerTests(unittest.TestCase):
    def test_raster_crosses_wrapped_x_y_and_corner_seams_without_map_chord(self):
        hm = flat_heightmap(-2, 2, -2, 2)
        topology = hydro_topology(hm, Mode.WRAPPED)
        for segment, expected in (
            (((2, 0), (3, 0)), {(2, 0), (-2, 0)}),
            (((0, 2), (0, 3)), {(0, 2), (0, -2)}),
            (((2, 2), (3, 3)), {(2, 2), (-2, -2)}),
        ):
            self.assertEqual(rasterize_segments([segment], topology=topology), expected)

    def test_sphere_raster_folds_both_edges_and_keeps_authored_extent(self):
        topology = hydro_topology(flat_heightmap(0, 5, 0, 4), Mode.SPHERE)
        self.assertEqual(rasterize_segments([((0, 4), (0, 6))], topology=topology),
                         {(0, 4), (3, 4), (3, 3)})
        self.assertEqual(rasterize_segments([((0, 0), (0, -2))], topology=topology),
                         {(0, 0), (3, 0), (3, 1)})

    def test_planar_raster_clips_cells_without_dropping_crossing_segment(self):
        topology = hydro_topology(flat_heightmap(-2, 2, -2, 2))
        self.assertEqual(rasterize_segments([((-4, 0), (0, 0))], topology=topology),
                         {(-2, 0), (-1, 0), (0, 0)})
        self.assertEqual(rasterize_segments([((-4, 4), (0, 4))], topology=topology), set())


    def test_fine_loader_reanchors_coastline_then_facade_floods_across_world_seam(self):
        hm = flat_heightmap(-2, 2, -2, 2)
        topology = hydro_topology(hm, Mode.WRAPPED)
        world = coastline_world(
            fine_cells_per_map_cell=1000, world_bounds=topology.bounds.model_dump(),
            z_min=-100,
            path=[waypoint(3500, -1000), waypoint(3500, 1000)],
            hydrology={"default_seas": {"bands": {"min": 1, "max": 1},
                                       "autoresolve_coastal_sea": False, "autoresolve_open_ocean": False}},
        )
        master = build_hydrology_master_input(world, [])
        self.assertEqual(master.declared_coastline_segments, [((-2, -1), (-2, 1))])
        result, before_fill = carve_then_fill(
            world, hm, scopes=frozenset({HydrologyScope.COASTAL_SEA}),
        )
        self.assertEqual(result.cell_index.by_cell[(2, 0)].deepening_index, 1)
        self.assertTrue(result.cell_index.by_cell[(2, 0)].liquid_candidate)
        self.assertEqual(hm.surface_z, before_fill)
        self.assertTrue(result.cell_index.by_cell.keys() <= hm.surface_z.keys())

    def test_fine_loader_preserves_long_segment_and_multi_leg_connectivity(self):
        topology = hydro_topology(flat_heightmap(-2, 2, -2, 2), Mode.WRAPPED)
        world = coastline_world(
            fine_cells_per_map_cell=1000, world_bounds=topology.bounds.model_dump(),
            path=[waypoint(3500, 0), waypoint(10500, 0), waypoint(10500, 1000)],
        )
        segments = build_hydrology_master_input(world, []).declared_coastline_segments
        self.assertEqual(segments, [((-2, 0), (5, 0)), ((5, 0), (5, 1))])
        self.assertEqual(rasterize_segments(segments, topology=topology),
                         {(x, 0) for x in range(-2, 3)} | {(0, 1)})

    def test_fine_loader_reflects_sphere_frame_before_rasterization(self):
        topology = hydro_topology(flat_heightmap(0, 5, 0, 4), Mode.SPHERE)
        world = coastline_world(
            fine_cells_per_map_cell=100, world_bounds=topology.bounds.model_dump(),
            world_topology_mode=Mode.SPHERE.value,
            path=[waypoint(0, 500), waypoint(100, 600), waypoint(200, 600)],
        )
        segments = build_hydrology_master_input(world, []).declared_coastline_segments
        self.assertEqual(segments, [((3, 4), (4, 3)), ((4, 3), (5, 3))])
        self.assertEqual(rasterize_segments(segments, topology=topology), {(3, 4), (4, 3), (5, 3)})


if __name__ == "__main__":
    unittest.main()
