"""Unit tests for hydrology sea/ocean carve — D HY-2."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.load.buildHydrologyMasterInput import (
    build_hydrology_master_input,
)
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import (
    carve_deepening_bands,
    flood_water_side,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.geom.polylineRasterize import (
    bresenham_line,
    rasterize_segments,
)
from app.application.worldData.generators.hydrology.basins.seaLevelPolicy import (
    is_land,
    resolve_z_sea,
)
from app.application.worldData.generators.hydrology.types import HydrologyBands, HydrologyScope
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole


def _world(**kwargs):
    defaults = {
        "world_uid": "test-world",
        "hydrology": {
            "enabled": True,
            "default_seas": {"bands": {"min": 1, "max": 3}},
        },
        "map_cell_size_m": 3000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _flat_heightmap(gx_lo: int, gx_hi: int, gy_lo: int, gy_hi: int, z: int = 5) -> SurfaceHeightmap:
    surface_z = {
        (gx, gy): z
        for gx in range(gx_lo, gx_hi + 1)
        for gy in range(gy_lo, gy_hi + 1)
    }
    return SurfaceHeightmap(
        world_uid="test-world",
        bbox=GridBBox(gx_lo, gx_hi, gy_lo, gy_hi),
        surface_z=surface_z,
    )


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
        self.assertFalse(is_land(0, 0))


class TestDeepeningBands(unittest.TestCase):

    def test_flood_water_side_north_of_east_west_coast(self):
        hm = _flat_heightmap(0, 10, 0, 6)
        segments = [((2, 2), (8, 2))]
        dist = flood_water_side(hm, rasterize_segments(segments), segments)
        self.assertIn((5, 1), dist)
        self.assertNotIn((5, 3), dist)

    def test_carve_sets_z_sea_and_roles(self):
        hm = _flat_heightmap(0, 10, 0, 6)
        segments = [((2, 2), (8, 2))]
        result = carve_deepening_bands(hm, segments, HydrologyBands(min=1, max=1), z_sea=0)
        self.assertEqual(hm.surface_z[(5, 1)], 1)  # deepening band 1
        self.assertEqual(hm.surface_z[(5, 0)], 0)  # beyond max band → open water
        entry = result.by_cell[(5, 0)]
        self.assertEqual(entry.role, HydrologyCellRole.COASTAL_SEA)
        self.assertTrue(result.dirty_bbox is not None)


class TestHydrologyOceanScope(unittest.TestCase):

    def _world_with_declared_coastline(self):
        return _world(hydrology={
            "enabled": True,
            "default_seas": {"bands": {"min": 1, "max": 3}},
            "declared_coastlines": [{
                "location_uid": "loc-sea",
                "path": [
                    {"x": 6000, "y": 6000, "z": 0},
                    {"x": 24000, "y": 6000, "z": 0},
                ],
            }],
        })

    def test_apply_ocean_scope_modifies_heightmap(self):
        w = self._world_with_declared_coastline()
        hm = _flat_heightmap(0, 12, 0, 6)
        svc = HydrologyGeneratorService()
        result = svc.apply(
            w,
            [],
            hm,
            scopes=frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}),
        )
        self.assertGreater(result.cells_modified, 0)
        self.assertTrue(any(z == 0 for z in hm.surface_z.values()))
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
