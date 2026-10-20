"""HY-12 step 3a: pure basin bathymetry modules — profile, distance field, absolute write."""

import unittest

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.reliefObjects.bathymetry import (
    BasinSpec, apply_basin_z, distance_from_boundary, floor_profile_z,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.bands import HydrologyBands
from app.dataModel.hydrology.enums.basinKind import BasinKind, basin_kind_profile
from tests.test_placement_resolver import topology


def heightmap(mode="planar", *, z=5, x_max=19, y_max=11):
    return SurfaceHeightmap(
        world_uid="world",
        bbox=GridBBox(0, x_max, 0, y_max),
        surface_z={(x, y): z for x in range(x_max + 1) for y in range(y_max + 1)},
    )


def spec(uid="basin", *, footprint, level=5, floor_z=0, kind=BasinKind.LAKE,
         bands=(1, 3)):
    return BasinSpec(source_uid=uid, kind=kind, liquid="water", footprint=frozenset(footprint),
                     z_water_level=level, floor_z=floor_z,
                     bands=HydrologyBands(min=bands[0], max=bands[1]))


class FloorProfileTests(unittest.TestCase):
    def test_bowl_is_monotone_and_bounded(self):
        bands = HydrologyBands(min=1, max=4)
        profile = basin_kind_profile(BasinKind.LAKE)
        zs = [floor_profile_z(d, level=5, floor_z=0, bands=bands, profile=profile)
              for d in range(1, 8)]
        self.assertEqual(zs, sorted(zs, reverse=True))
        self.assertLess(zs[0], 5)
        self.assertTrue(all(0 <= z <= 4 for z in zs))
        self.assertTrue(all(z == 0 for z in zs[4:]))  # d > D_slope → floor

    def test_shelf_profile_matches_bowl_at_rim_and_differs_on_shelf(self):
        bands = HydrologyBands(min=2, max=6)
        bowl = basin_kind_profile(BasinKind.LAKE)
        shelf = basin_kind_profile(BasinKind.SEA)
        at_shelf_edge = floor_profile_z(2, level=5, floor_z=-10, bands=bands, profile=shelf)
        bowl_same = floor_profile_z(2, level=5, floor_z=-10, bands=bands, profile=bowl)
        self.assertNotEqual(at_shelf_edge, bowl_same)
        # d=1 lerps top(4) → z_shelf(4 - round(14*0.30)=0) at t=1/2 → 2.
        self.assertEqual(floor_profile_z(1, level=5, floor_z=-10, bands=bands, profile=shelf), 2)
        self.assertEqual(floor_profile_z(7, level=5, floor_z=-10, bands=bands, profile=shelf), -10)

    def test_equal_shelf_and_slope_distances_drop_to_floor(self):
        bands = HydrologyBands(min=3, max=3)
        profile = basin_kind_profile(BasinKind.OCEAN)
        self.assertEqual(floor_profile_z(4, level=5, floor_z=-2, bands=bands, profile=profile), -2)

    def test_zero_depth_stays_at_top(self):
        bands = HydrologyBands(min=1, max=3)
        for profile in (basin_kind_profile(BasinKind.LAKE), basin_kind_profile(BasinKind.SEA)):
            self.assertTrue(all(
                floor_profile_z(d, level=5, floor_z=4, bands=bands, profile=profile) == 4
                for d in range(1, 6)))


class DistanceFieldTests(unittest.TestCase):
    def test_planar_block_distances(self):
        cells = frozenset((x, y) for x in range(2, 8) for y in range(2, 8))
        dist = distance_from_boundary(cells, topology(x_max=19, y_max=11))
        border = {(x, y) for x, y in cells if x in (2, 7) or y in (2, 7)}
        self.assertTrue(all(dist[cell] == 1 for cell in border))
        self.assertEqual(dist[(4, 4)], 3)
        self.assertEqual(dist[(5, 5)], 3)

    def test_wrapped_seam_symmetry_and_full_world(self):
        topo = topology("wrapped", x_max=19, y_max=11)
        cells = frozenset((x, y) for x in (18, 19, 0, 1) for y in range(3))
        dist = distance_from_boundary(cells, topo)
        for y in range(3):
            self.assertEqual(dist[(18, y)], dist[(1, y)])
            self.assertEqual(dist[(19, y)], dist[(0, y)])
        self.assertEqual(dist[(19, 1)], 2)
        world = frozenset((x, y) for x in range(20) for y in range(12))
        self.assertEqual(distance_from_boundary(world, topo), {})


class ApplyBasinZTests(unittest.TestCase):
    def test_absolute_write_inside_only_and_idempotent(self):
        hm = heightmap(z=5)
        footprint = {(x, y) for x in range(2, 6) for y in range(2, 6)}
        written = apply_basin_z(hm, [spec(footprint=footprint)], topology(x_max=19, y_max=11),
                                reserved=frozenset())
        self.assertEqual(written, 16)
        self.assertTrue(all(hm.surface_z[cell] < 5 for cell in footprint))
        self.assertEqual(hm.surface_z[(6, 6)], 5)
        snapshot = dict(hm.surface_z)
        apply_basin_z(hm, [spec(footprint=footprint)], topology(x_max=19, y_max=11),
                      reserved=frozenset())
        self.assertEqual(hm.surface_z, snapshot)

    def test_overlap_takes_min_of_profiles(self):
        hm = heightmap(z=5)
        a = {(x, y) for x in range(2, 6) for y in range(2, 6)}
        b = {(x, y) for x in range(4, 8) for y in range(4, 8)}
        shallow = spec("a", footprint=a, floor_z=0)
        deep = spec("b", footprint=b, floor_z=-4)
        apply_basin_z(hm, [deep, shallow], topology(x_max=19, y_max=11), reserved=frozenset())
        shared = a & b
        self.assertTrue(shared)
        deep_only = apply_basin_z(heightmap(z=5), [deep], topology(x_max=19, y_max=11),
                                  reserved=frozenset())
        self.assertEqual(deep_only, len(b))
        for cell in shared:
            reference = spec("b", footprint=b, floor_z=-4)
            hm2 = heightmap(z=5)
            apply_basin_z(hm2, [reference], topology(x_max=19, y_max=11), reserved=frozenset())
            self.assertEqual(hm.surface_z[cell], hm2.surface_z[cell])

    def test_reserved_cell_keeps_height_and_neighbors_become_boundary(self):
        hm = heightmap(z=5)
        footprint = {(x, y) for x in range(2, 7) for y in range(2, 7)}
        topo = topology(x_max=19, y_max=11)
        apply_basin_z(hm, [spec(footprint=footprint)], topo, reserved=frozenset({(4, 4)}))
        self.assertEqual(hm.surface_z[(4, 4)], 5)
        bands = HydrologyBands(min=1, max=3)
        expected = floor_profile_z(1, level=5, floor_z=0, bands=bands,
                                   profile=basin_kind_profile(BasinKind.LAKE))
        for neighbor in ((4, 3), (4, 5), (3, 4), (5, 4)):
            self.assertEqual(hm.surface_z[neighbor], expected)

    def test_footprint_outside_heightmap_is_input_error(self):
        hm = heightmap(z=5)
        footprint = {(25, 3), (26, 3)}
        with self.assertRaises(ValueError):
            apply_basin_z(hm, [spec(footprint=footprint)], topology(x_max=19, y_max=11),
                          reserved=frozenset())


if __name__ == "__main__":
    unittest.main()
