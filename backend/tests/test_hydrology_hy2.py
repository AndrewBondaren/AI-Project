"""Unit tests for hydrology sea/ocean carve — D HY-2."""

import unittest

from tests.hydrology_fixtures import hydro_topology

from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from tests.hydrology_geometry_helpers import (flood_water_side)
from app.application.worldData.generators.hydrology.geom.polylineRasterize import (
    bresenham_line,
    rasterize_segments,
)
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import (
    is_land,
    resolve_z_sea,
)
from app.application.worldData.generators.hydrology.types import (
    HydrologyScope,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole


from tests.hydrology_fixtures import (
    coastline_world,
    carve_then_fill,
    flat_heightmap as _flat_heightmap,
    hydro_world,
    seas_hydrology,
)


def _world(**kwargs):
    kwargs.setdefault("hydrology", seas_hydrology(bands=(1, 3), autoresolve=False))
    return hydro_world(**kwargs)


class TestPolylineRasterize(unittest.TestCase):

    def test_bresenham_horizontal(self):
        cells = bresenham_line(2, 4, 5, 4)
        self.assertEqual(cells, [(2, 4), (3, 4), (4, 4), (5, 4)])

    def test_rasterize_segments_union(self):
        segs = [((0, 0), (2, 0)), ((2, 0), (2, 2))]
        cells = rasterize_segments(segs)
        self.assertIn((1, 0), cells)
        self.assertIn((2, 1), cells)
        self.assertEqual(len(cells), 5)


class TestSeaLevelPolicy(unittest.TestCase):

    def test_z_sea_zero(self):
        self.assertEqual(resolve_z_sea(_world()), 0)

    def test_is_land(self):
        self.assertTrue(is_land(3, 0))
        self.assertTrue(is_land(0, 0))


class TestDeepeningBands(unittest.TestCase):

    def test_flood_water_side_north_of_east_west_coast(self):
        hm = _flat_heightmap(0, 10, 0, 6)
        segments = [((2, 2), (8, 2))]
        dist = flood_water_side(hm, rasterize_segments(segments), segments, topology=hydro_topology(hm))
        self.assertIn((5, 1), dist)
        self.assertNotIn((5, 3), dist)


class TestHydrologyOceanScope(unittest.TestCase):

    def _world_with_declared_coastline(self):
        return coastline_world(bands=(1, 3), autoresolve=False)

    def test_carve_then_fill_ocean_scope_preserves_bottom(self):
        w = self._world_with_declared_coastline()
        w.z_min = -100
        hm = _flat_heightmap(0, 12, 0, 6)
        result, before_fill = carve_then_fill(
            w, hm,
            scopes=frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}),
        )
        self.assertGreater(result.cells_modified, 0)
        self.assertEqual(hm.surface_z, before_fill)
        self.assertTrue(any(z < 0 for z in hm.surface_z.values()))
        roles = set(result.cell_index.roles.values())
        self.assertTrue(
            roles & {HydrologyCellRole.COASTAL_SEA, HydrologyCellRole.OPEN_OCEAN, HydrologyCellRole.SHORE},
        )

    def test_master_input_extracts_coastline_segments(self):
        w = self._world_with_declared_coastline()
        inp = build_hydrology_master_input(w, [], [], [])
        self.assertEqual(len(inp.declared_coastline_segments), 1)
        self.assertEqual(inp.declared_coastline_segments[0], ((2, 2), (8, 2)))


if __name__ == "__main__":
    unittest.main()
