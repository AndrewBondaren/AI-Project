"""Unit tests for lake basin carve — D HY-3."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.basins.lakeBasinGenerator import carve_lake_basin
from app.application.worldData.generators.hydrology.geom.polygonInterior import (
    interior_cells,
    point_in_polygon,
)
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.types import HydrologyBands, LakeSpec
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole


def _flat(gx_lo: int, gx_hi: int, gy_lo: int, gy_hi: int, z: int = 8) -> SurfaceHeightmap:
    surface_z = {
        (gx, gy): z
        for gx in range(gx_lo, gx_hi + 1)
        for gy in range(gy_lo, gy_hi + 1)
    }
    return SurfaceHeightmap(
        world_uid="test",
        bbox=GridBBox(gx_lo, gx_hi, gy_lo, gy_hi),
        surface_z=surface_z,
    )


class TestPolygonInterior(unittest.TestCase):

    def test_point_in_unit_square(self):
        verts = [(0.0, 0.0), (3.0, 0.0), (3.0, 3.0), (0.0, 3.0)]
        self.assertTrue(point_in_polygon(1.5, 1.5, verts))
        self.assertFalse(point_in_polygon(4.5, 1.5, verts))


class TestLakeBasin(unittest.TestCase):

    def test_carve_closed_quad_has_lake_center(self):
        segments = [
            ((4, 4), (7, 4)),
            ((7, 4), (7, 7)),
            ((7, 7), (4, 7)),
            ((4, 7), (4, 4)),
        ]
        hm = _flat(0, 10, 0, 10)
        spec = LakeSpec(shoreline_segments=segments)
        carved = carve_lake_basin(hm, spec, HydrologyBands(min=1, max=3))
        shoreline = rasterize_segments(segments)
        interior = interior_cells(hm, segments, shoreline)
        self.assertTrue(interior)
        lake_cells = [c for c, e in carved.items() if e.role == HydrologyCellRole.LAKE]
        self.assertTrue(lake_cells)
        self.assertTrue(all(hm.surface_z[c] < 8 for c in lake_cells))


if __name__ == "__main__":
    unittest.main()
