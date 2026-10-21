"""Unit tests for procedural sea/ocean autoresolve — D HY-5a."""

import unittest

from tests.hydrology_fixtures import hydro_topology

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import (
    declare_coastline_bbox_padded,
    flood_water_side,
    flood_water_side_unbounded,
)
from app.application.worldData.generators.hydrology.load.hydrologyAutoresolvePolicy import (
    seas_autoresolve_policy,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.autoresolve.proceduralSeaAutoresolve import (
    autoresolve_sea_basins,
)
from app.application.worldData.generators.hydrology.types import (
    CoastlineSpec,
    HydrologyMasterInput,
    HydrologyScope,
    LoadedConnectionGraph,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from tests.hydrology_fixtures import (
    coastline_world as _world_with_coastline,
    flat_heightmap as _flat_heightmap,
    hydro_world,
    seas_hydrology,
)


def _world(**kwargs):
    kwargs.setdefault("hydrology", seas_hydrology())
    return hydro_world(**kwargs)


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
        bounded = flood_water_side(hm, coastline, segments, topology=hydro_topology(hm))
        unbounded = flood_water_side_unbounded(hm, coastline, segments, topology=hydro_topology(hm))
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
            declared_coastline_specs=[CoastlineSpec(segments=segments, location_uid="loc-sea")],
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
            declared_coastline_specs=[CoastlineSpec(segments=segments, location_uid="loc-sea")],
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
        from app.application.worldData.generators.hydrology.shore.deepeningBandCarver import (
            flood_from_bbox_ocean_edge,
        )
        dist = flood_from_bbox_ocean_edge(hm, topology=hydro_topology(hm))
        self.assertIn((5, 0), dist)
        self.assertNotIn((5, 6), dist)

    def test_service_without_declare_coastline(self):
        w = _world()
        hm = _flat_heightmap(0, 12, 0, 6, z=-5)
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
            declared_coastline_specs=[],
        )
        svc = HydrologyGeneratorService()
        result = svc.apply(w, [], hm, master=master)
        roles = {entry.role for entry in result.cell_index.by_cell.values()}
        self.assertIn(HydrologyCellRole.OPEN_OCEAN, roles)
        self.assertGreater(result.cells_modified, 20)


class TestHydrologyServiceAutoresolve(unittest.TestCase):

    def test_autoresolve_reads_existing_depression_outside_declare_strip(self):
        w = _world_with_coastline()
        hm = _flat_heightmap(0, 12, 0, 6, z=-5)
        before = dict(hm.surface_z)
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
        self.assertEqual(hm.surface_z, before)

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
