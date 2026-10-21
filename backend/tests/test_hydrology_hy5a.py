"""Unit tests for procedural sea/ocean autoresolve — D HY-5a."""

import unittest

from tests.hydrology_fixtures import hydro_topology

from tests.hydrology_geometry_helpers import (flood_water_side, flood_water_side_unbounded)
from app.application.worldData.generators.hydrology.load.hydrologyAutoresolvePolicy import (
    seas_autoresolve_policy,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.geom.polylineRasterize import rasterize_segments
from app.application.worldData.generators.hydrology.types import (
    HydrologyMasterInput,
    HydrologyScope,
    LoadedConnectionGraph,
)
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
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


class TestBoundaryAutoresolve(unittest.TestCase):

    def test_high_flat_world_is_not_synthesized_into_an_ocean(self):
        hm = _flat_heightmap(0, 10, 0, 6, z=5)
        before = dict(hm.surface_z)
        result = HydrologyGeneratorService().apply(_world(), [], hm,
            scopes=frozenset({HydrologyScope.OPEN_OCEAN}))
        self.assertEqual(result.cell_index.by_cell, {})
        self.assertEqual(hm.surface_z, before)

    def test_below_default_ocean_does_not_depend_on_world_edge(self):
        for mode in ("planar", "wrapped", "sphere"):
            with self.subTest(mode=mode):
                hm = _flat_heightmap(0, 5, 0, 4, z=-5)
                result = HydrologyGeneratorService().apply(_world(world_topology_mode=mode), [], hm,
                    scopes=frozenset({HydrologyScope.OPEN_OCEAN}))
                self.assertEqual(set(result.cell_index.by_cell), set(hm.surface_z))
                self.assertEqual(len(result.water_bodies), 1)
                self.assertEqual(result.water_bodies[0].z_water_level, 0)

    def test_equal_level_flat_world_stays_dry(self):
        hm = _flat_heightmap(0, 5, 0, 4, z=0)
        result = HydrologyGeneratorService().apply(_world(), [], hm,
            scopes=frozenset({HydrologyScope.OPEN_OCEAN}))
        self.assertEqual(result.cell_index.by_cell, {})


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
