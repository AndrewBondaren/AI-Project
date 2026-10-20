"""HY-6 matrix A1–C: nearest-segment water side, endpoints, and footprint seam."""

import json
import tempfile
import unittest

from tests.hydrology_fixtures import hydro_topology
from pathlib import Path

from app.application.worldData.generators.hydrology.basins.seaBasinGenerator import generate_coastal_sea
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import (
    _land_shore_cells,
    carve_deepening_bands,
    compute_land_centroid,
    flood_water_side,
    flood_water_side_unbounded,
    water_side_seeds,
)
from app.application.worldData.generators.hydrology.shore.waterSideFootprint import (
    CoastlineWaterSide,
    water_side_footprint,
)
from app.application.worldData.generators.hydrology.types import CoastlineSpec, HydrologyBands
from app.core.generationLogging import generation_world_log
from tests.hydrology_fixtures import flat_heightmap, hydro_master, hydro_world, seas_hydrology


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
        before = dict(self.hm.surface_z)
        result = carve_deepening_bands(self.hm, segments, HydrologyBands(min=1, max=1),
                                      water_body_uid="test-sea", z_sea=0, topology=self.topology)
        self.assertEqual(result.by_cell[(3, 3)].deepening_index, 0)
        self.assertEqual(result.by_cell[(1, 3)].deepening_index, 1)
        # Declared-source z is carved by Pass 1.4 basinZ (HY-12/3b); carver is role-only.
        self.assertEqual(self.hm.surface_z, before)

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


class TestCoastlineWarnings(unittest.TestCase):
    LOGGER = "app.application.worldData.generators.hydrology.basins.seaBasinGenerator"

    def generate(self, x, *, bands=(2, 3), segments=None):
        world = hydro_world(hydrology=seas_hydrology(bands=bands), world_topology_mode="planar")
        spec = CoastlineSpec(
            segments=segments if segments is not None else [((x, 1), (x, 5))],
            location_uid="loc-sea-warning",
        )
        return generate_coastal_sea(
            world, flat_heightmap(0, 10, 0, 6),
            hydro_master(declared_coastline_specs=[spec]),
        )

    def test_empty_water_warns_even_with_land_shore(self):
        with self.assertLogs(self.LOGGER, level="WARNING") as captured:
            cells, _ = self.generate(0)
        self.assertTrue(cells)  # Shore alone must not hide the empty flood.
        self.assertEqual(len(captured.records), 1)
        self.assertIn("water_dist=0 (water side outside bounds?)", captured.output[0])
        self.assertIn("world=test-world", captured.output[0])
        self.assertIn("water_body_uid=loc-sea-warning", captured.output[0])

    def test_narrow_water_warns_including_exact_minimum(self):
        for extent in (1, 2):
            with self.subTest(extent=extent):
                with self.assertLogs(self.LOGGER, level="WARNING") as captured:
                    self.generate(extent)
                self.assertEqual(len(captured.records), 1)
                self.assertIn(f"water extent {extent} <= bands.min 2: no open water", captured.output[0])

    def test_open_water_does_not_warn(self):
        with self.assertNoLogs(self.LOGGER, level="WARNING"):
            self.generate(4)

    def test_empty_and_degenerate_line_do_not_report_empty_water_warning(self):
        with self.assertNoLogs(self.LOGGER, level="WARNING"):
            self.generate(0, segments=[])
            self.generate(0, segments=[((-5, 1), (-5, 1))])

    def test_both_warnings_reach_generation_log_and_latest(self):
        with tempfile.TemporaryDirectory() as root:
            with generation_world_log("test-world", mode="light", root=root) as run_path:
                self.generate(0)
                self.generate(1)
            rows = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines()]
            warnings = [row for row in rows if row["level"] == "WARNING" and row["logger"] == self.LOGGER]
            self.assertEqual(len(warnings), 2)
            self.assertIn("water_dist=0", warnings[0]["msg"])
            self.assertIn("water extent 1 <= bands.min 2", warnings[1]["msg"])
            latest = Path(root) / "test-world" / "bake-light-latest.log"
            self.assertEqual(latest.read_text(encoding="utf-8"), run_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
