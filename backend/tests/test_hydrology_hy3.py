"""Unit tests for lake basin carve — D HY-3."""

import unittest

from app.application.worldData.generators.hydrology.geom.polygonInterior import (
    point_in_polygon,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from tests.hydrology_fixtures import flat_heightmap


class TestPolygonInterior(unittest.TestCase):

    def test_point_in_unit_square(self):
        verts = [(0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)]
        self.assertTrue(point_in_polygon(1.5, 1.5, verts))
        self.assertFalse(point_in_polygon(4.5, 1.5, verts))


class TestUnifiedLakeBasin(unittest.TestCase):
    def test_declared_ring_materializes_lake_center_and_dry_shore(self):
        from tests.test_hydrology_hy12_smoke import basin_world
        from tests.hydrology_fixtures import carve_then_fill
        hm = flat_heightmap(0, 7, 0, 5, z=8)
        result, before_fill = carve_then_fill(basin_world(source="lake"), hm)
        self.assertEqual(hm.surface_z, before_fill)
        center = result.cell_index.by_cell[(3, 2)]
        self.assertEqual(center.water_body_uid, "body")
        self.assertTrue(center.liquid_candidate)
        self.assertLess(hm.surface_z[(3, 2)], center.z_water_level)
        shores = {cell: entry for cell, entry in result.cell_index.by_cell.items()
                  if entry.role == HydrologyCellRole.SHORE}
        self.assertTrue(shores)
        self.assertTrue(all(not entry.liquid_candidate for entry in shores.values()))


if __name__ == "__main__":
    unittest.main()
