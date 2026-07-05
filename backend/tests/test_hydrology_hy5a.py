"""Unit tests for procedural sea/ocean autoresolve — D HY-5a."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.hydrology.deepeningBandCarver import (
    declare_coastline_bbox_padded,
    flood_water_side,
    flood_water_side_unbounded,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyAutoresolvePolicy import (
    seas_autoresolve_policy,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.hydrology.polylineRasterize import rasterize_segments
from app.application.worldData.generators.terrain.hydrology.proceduralSeaAutoresolve import (
    autoresolve_sea_basins,
)
from app.application.worldData.generators.terrain.hydrology.types import (
    HydrologyMasterInput,
    HydrologyScope,
    LoadedConnectionGraph,
)
from app.application.worldData.generators.terrain.types import SurfaceHeightmap
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology


def _world(**kwargs):
    defaults = {
        "world_uid": "test-world",
        "hydrology": {
            "enabled": True,
            "default_seas": {
                "bands": {"min": 1, "max": 2},
                "autoresolve_coastal_sea": True,
                "autoresolve_open_ocean": True,
            },
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


def _world_with_coastline(**kwargs):
    base = {
        "enabled": True,
        "default_seas": {
            "bands": {"min": 1, "max": 2},
            "autoresolve_coastal_sea": True,
            "autoresolve_open_ocean": True,
        },
        "declared_coastlines": [{
            "location_uid": "loc-sea",
            "path": [
                {"x": 6000, "y": 6000, "z": 0},
                {"x": 24000, "y": 6000, "z": 0},
            ],
        }],
    }
    if "hydrology" in kwargs:
        merged = {**base, **kwargs.pop("hydrology")}
        return _world(hydrology=merged, **kwargs)
    return _world(hydrology=base, **kwargs)


class TestSeasAutoresolvePolicy(unittest.TestCase):

    def test_defaults_on(self):
        policy = seas_autoresolve_policy(_world())
        self.assertTrue(policy.seas_enabled)
        self.assertTrue(policy.autoresolve_coastal_sea)
        self.assertTrue(policy.autoresolve_open_ocean)

    def test_explicit_off(self):
        policy = seas_autoresolve_policy(
            _world(
                hydrology={
                    "enabled": True,
                    "default_seas": {
                        "autoresolve_coastal_sea": False,
                        "autoresolve_open_ocean": False,
                    },
                },
            ),
        )
        self.assertFalse(policy.autoresolve_coastal_sea)
        self.assertFalse(policy.autoresolve_open_ocean)


class TestUnboundedFlood(unittest.TestCase):

    def test_reaches_outside_coast_gx_strip(self):
        hm = _flat_heightmap(0, 10, 0, 6)
        segments = [((2, 2), (8, 2))]
        coastline = rasterize_segments(segments)
        bounded = flood_water_side(hm, coastline, segments)
        unbounded = flood_water_side_unbounded(hm, coastline, segments)
        self.assertNotIn((0, 1), bounded)
        self.assertIn((0, 1), unbounded)
        self.assertIn((10, 0), unbounded)

    def test_declare_bbox_padding(self):
        segments = [((2, 2), (8, 2))]
        bbox = declare_coastline_bbox_padded(segments)
        self.assertEqual(bbox, GridBBox(1, 9, 1, 3))


class TestProceduralSeaAutoresolve(unittest.TestCase):

    def test_skips_occupied_and_inside_bbox(self):
        hm = _flat_heightmap(0, 10, 0, 6)
        segments = [((2, 2), (8, 2))]
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.COASTAL_SEA}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
            declared_coastline_segments=segments,
        )
        occupied = {(5, 1): MapCellHydrology(role=HydrologyCellRole.SHORE)}
        auto, bbox = autoresolve_sea_basins(
            _world(),
            hm,
            master,
            occupied,
            autoresolve_coastal=True,
            autoresolve_open_ocean=True,
        )
        self.assertNotIn((5, 1), auto)
        self.assertIn((0, 1), auto)
        self.assertTrue(bbox is not None)

    def test_disabled_flags_return_empty(self):
        hm = _flat_heightmap(0, 10, 0, 6)
        segments = [((2, 2), (8, 2))]
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.COASTAL_SEA}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
            declared_coastline_segments=segments,
        )
        auto, bbox = autoresolve_sea_basins(
            _world(),
            hm,
            master,
            {},
            autoresolve_coastal=False,
            autoresolve_open_ocean=False,
        )
        self.assertEqual(auto, {})
        self.assertIsNone(bbox)


class TestBoundaryAutoresolve(unittest.TestCase):

    def test_flood_from_bbox_north_ocean(self):
        hm = _flat_heightmap(0, 10, 0, 6)
        from app.application.worldData.generators.terrain.hydrology.deepeningBandCarver import (
            flood_from_bbox_ocean_edge,
        )
        dist = flood_from_bbox_ocean_edge(hm)
        self.assertIn((5, 0), dist)
        self.assertNotIn((5, 6), dist)

    def test_service_without_declare_coastline(self):
        w = _world()
        hm = _flat_heightmap(0, 12, 0, 6)
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
            declared_coastline_segments=[],
        )
        svc = HydrologyGeneratorService()
        result = svc.apply(w, [], hm, master=master)
        roles = {entry.role for entry in result.cell_index.by_cell.values()}
        self.assertIn(HydrologyCellRole.OPEN_OCEAN, roles)
        self.assertGreater(result.cells_modified, 20)


class TestHydrologyServiceAutoresolve(unittest.TestCase):

    def test_apply_adds_open_ocean_outside_declare_strip(self):
        w = _world_with_coastline()
        hm = _flat_heightmap(0, 12, 0, 6)
        svc = HydrologyGeneratorService()
        result = svc.apply(
            w,
            [],
            hm,
            scopes=frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}),
        )
        roles = result.cell_index.by_cell
        self.assertIn((0, 0), roles)
        self.assertEqual(roles[(0, 0)].role, HydrologyCellRole.OPEN_OCEAN)
        self.assertGreater(result.cells_modified, 12)

    def test_autoresolve_off_keeps_narrow_strip(self):
        w = _world(
            hydrology={
                "enabled": True,
                "default_seas": {
                    "bands": {"min": 1, "max": 2},
                    "autoresolve_coastal_sea": False,
                    "autoresolve_open_ocean": False,
                },
            },
        )
        hm = _flat_heightmap(0, 12, 0, 6)
        svc = HydrologyGeneratorService()
        result = svc.apply(
            w,
            [],
            hm,
            scopes=frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}),
        )
        roles = result.cell_index.by_cell
        self.assertNotIn((0, 0), roles)


if __name__ == "__main__":
    unittest.main()
