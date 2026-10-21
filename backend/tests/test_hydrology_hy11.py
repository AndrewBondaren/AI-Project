"""HY-11 declared flood: world seams, canonical passability and unrolled normals."""

import unittest

from app.application.worldData.generators.hydrology.basins.seaBasinGenerator import generate_coastal_sea
from app.application.worldData.generators.hydrology.autoresolve.proceduralSeaAutoresolve import autoresolve_sea_basins
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import HydrologyGeneratorService
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import build_hydrology_master_input
from app.application.worldData.generators.hydrology.load.resolveHydrologyTopology import resolve_hydrology_topology
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import (
    carve_deepening_bands, compute_land_centroid, flood_from_bbox_ocean_edge,
    flood_water_side, flood_water_side_unbounded,
)
from app.application.worldData.generators.hydrology.shore.waterSideFootprint import (
    CoastlineWaterSide, water_side_footprint,
)
from app.application.worldData.generators.hydrology.types import CoastlineSpec, HydrologyBands, HydrologyScope
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.topology.enums.worldTopologyMode import WorldTopologyMode as Mode
from tests.hydrology_fixtures import (
    coastline_world, flat_heightmap, hydro_master, hydro_topology, hydro_world, seas_hydrology, waypoint,
    carve_then_fill,
)


class DeclaredTopologyFloodTests(unittest.TestCase):
    LOGGER = "app.application.worldData.generators.hydrology.basins.seaBasinGenerator"

    def setUp(self):
        self.hm = flat_heightmap(-2, 2, -2, 2)
        self.topology = hydro_topology(self.hm, Mode.WRAPPED)
        self.segments = [((-2, -1), (-2, 1))]

    def geometry(self, segments=None, centroid=(0, 0)):
        segments = self.segments if segments is None else segments
        return CoastlineWaterSide(rasterize_segments(segments), segments, centroid,
                                  topology=self.topology)

    def generate(self, *, world=None, hm=None, segments=None):
        world = world or hydro_world(hydrology=seas_hydrology(bands=(1, 1)))
        spec = CoastlineSpec(segments=self.segments if segments is None else segments,
                             location_uid="hy11-sea")
        return generate_coastal_sea(world, self.hm if hm is None else hm,
                                    hydro_master(declared_coastline_specs=[spec]))

    def test_wrapped_west_coast_flood_reaches_east_with_canonical_distances(self):
        water = flood_water_side(self.hm, rasterize_segments(self.segments), self.segments,
                                 topology=self.topology)
        self.assertEqual(water, {(x, y): 3 - x for x in (1, 2) for y in (-1, 0, 1)})
        self.assertEqual(self.hm.surface_z, flat_heightmap(-2, 2, -2, 2).surface_z)
        self.assertLessEqual(len(water), len(self.hm.surface_z))

    def test_declared_carver_writes_only_canonical_cells_and_leaves_land_intact(self):
        before = dict(self.hm.surface_z)
        result = carve_deepening_bands(self.hm, self.segments, HydrologyBands(min=1, max=1),
                                       topology=self.topology, water_body_uid="hy11-sea", z_sea=0)
        self.assertEqual(result.by_cell[(2, 0)].deepening_index, 1)
        self.assertEqual(result.by_cell[(1, 0)].role, HydrologyCellRole.COASTAL_SEA)
        self.assertEqual(result.by_cell[(-1, 0)].deepening_index, 0)
        # Declared-source z is carved by Pass 1.4 basinZ (HY-12/3b); carver is role-only.
        self.assertEqual(self.hm.surface_z[(1, 0)], before[(1, 0)])
        self.assertEqual(self.hm.surface_z[(-1, 0)], before[(-1, 0)])
        self.assertEqual(set(self.hm.surface_z), set(before))
        self.assertTrue(set(result.by_cell) <= before.keys())
        self.assertEqual(result.by_cell[(2, 0)].water_body_uid, "hy11-sea")

    def test_world_default_wrapped_does_not_emit_false_empty_water_warning(self):
        with self.assertNoLogs(self.LOGGER, level="WARNING"):
            cells, _ = self.generate()
        self.assertEqual(cells[(2, 0)].deepening_index, 1)
        self.assertEqual(cells[(1, 0)].role, HydrologyCellRole.COASTAL_SEA)

    def test_planar_void_warns_and_does_not_expand_heightmap(self):
        world = hydro_world(hydrology=seas_hydrology(bands=(1, 1)),
                             world_topology_mode=Mode.PLANAR.value)
        before = dict(self.hm.surface_z)
        with self.assertLogs(self.LOGGER, level="WARNING") as captured:
            cells, _ = self.generate(world=world)
        self.assertEqual(len(captured.records), 1)
        self.assertIn("water_dist=0", captured.output[0])
        self.assertTrue(cells)
        self.assertTrue(all(entry.deepening_index == 0 for entry in cells.values()))
        self.assertEqual(self.hm.surface_z, before)

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

    def test_missing_seam_target_is_not_created_and_world_bounds_override_bake_scope(self):
        partial = flat_heightmap(-2, 0, -2, 2)
        world = hydro_world(hydrology=seas_hydrology(bands=(1, 1)),
                             world_bounds=self.topology.bounds.model_dump())
        resolved = resolve_hydrology_topology(world, partial)
        self.assertEqual(resolved.bounds, self.topology.bounds)
        before = dict(partial.surface_z)
        with self.assertLogs(self.LOGGER, level="WARNING"):
            cells, _ = self.generate(world=world, hm=partial)
        self.assertEqual(partial.surface_z, before)
        self.assertNotIn((0, 0), cells)  # Partial bbox must not become a false wrap seam.

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

    def test_sphere_carver_uses_world_mode_and_keeps_normal_across_fold(self):
        for y in (0, 4):
            with self.subTest(y=y):
                hm = flat_heightmap(0, 5, 0, 4)
                world = hydro_world(world_topology_mode=Mode.SPHERE.value,
                                     hydrology=seas_hydrology(bands=(1, 1)))
                spec = CoastlineSpec(segments=[((0, y), (1, y))], location_uid="sphere-sea")
                cells, _ = generate_coastal_sea(world, hm, hydro_master(declared_coastline_specs=[spec]))
                self.assertEqual(cells[(3, y)].deepening_index, 1)
                self.assertEqual(cells[(3, 3 if y == 4 else 1)].role, HydrologyCellRole.COASTAL_SEA)
                self.assertEqual(cells[(3, y)].water_body_uid, "sphere-sea")

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

    def test_fully_clipped_planar_declare_keeps_empty_water_diagnostic(self):
        hm = flat_heightmap(-2, 2, -2, 2)
        world = hydro_world(world_topology_mode=Mode.PLANAR.value,
                             hydrology=seas_hydrology(bands=(1, 1)))
        spec = CoastlineSpec(segments=[((-4, -1), (-4, 1))], location_uid="void-sea")
        before = dict(hm.surface_z)
        with self.assertLogs(DeclaredTopologyFloodTests.LOGGER, level="WARNING") as captured:
            cells, _ = generate_coastal_sea(world, hm, hydro_master(declared_coastline_specs=[spec]))
        self.assertEqual(cells, {})
        self.assertEqual(len(captured.records), 1)
        self.assertIn("water_dist=0", captured.output[0])
        self.assertEqual(hm.surface_z, before)

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

    def test_padded_declared_bbox_excludes_its_wrapped_image_from_autoresolve(self):
        hm = flat_heightmap(-2, 2, -2, 2)
        master = hydro_master(declared_coastline_specs=[
            CoastlineSpec(segments=[((-2, -1), (-2, 1))], location_uid="hy11-sea"),
        ])
        auto, _ = autoresolve_sea_basins(
            hydro_world(hydrology=seas_hydrology(bands=(1, 1))), hm, master, {},
            autoresolve_coastal=True, autoresolve_open_ocean=True,
        )
        self.assertTrue(auto)
        self.assertNotIn((2, 0), auto)  # Image (-3,0) lies inside padded declare bbox.
        self.assertIn((1, 0), auto)

    def test_padded_declared_bbox_excludes_fold_image_from_autoresolve(self):
        hm = flat_heightmap(0, 5, 0, 4)
        master = hydro_master(declared_coastline_specs=[
            CoastlineSpec(segments=[((0, 4), (1, 4))], location_uid="hy11-sea"),
        ])
        auto, _ = autoresolve_sea_basins(
            hydro_world(world_topology_mode=Mode.SPHERE.value, hydrology=seas_hydrology(bands=(1, 1))),
            hm, master, {}, autoresolve_coastal=True, autoresolve_open_ocean=True,
        )
        self.assertNotIn((3, 4), auto)  # Reflected image (0,5) is inside padded bbox.
        self.assertIn((3, 3), auto)

    def test_procedural_partial_bake_edge_is_not_a_world_edge(self):
        for mode in Mode:
            full = flat_heightmap(-2, 3, -2, 2)
            topology = hydro_topology(full, mode)
            partial = flat_heightmap(-1, 1, -1, 1)
            self.assertEqual(flood_from_bbox_ocean_edge(partial, topology=topology), {})

    def test_procedural_flood_keeps_canonical_keys_for_every_topology(self):
        for mode in Mode:
            hm = flat_heightmap(-2, 3, -2, 2)
            water = flood_from_bbox_ocean_edge(hm, topology=hydro_topology(hm, mode))
            self.assertIn((0, -2), water)
            self.assertTrue(water.keys() <= hm.surface_z.keys())
            self.assertTrue(all(distance > 0 for distance in water.values()))


if __name__ == "__main__":
    unittest.main()
