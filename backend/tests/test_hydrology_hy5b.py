"""Unit tests for procedural lake autoresolve — D HY-5b."""

import unittest

from app.application.worldData.generators.hydrology.load.hydrologyAutoresolvePolicy import (
    lakes_autoresolve_policy,
)
from app.application.worldData.generators.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.hydrology.autoresolve.proceduralLakeAutoresolve import (
    autoresolve_lakes,
    flood_basin_interior,
)
from app.application.worldData.generators.hydrology.types import HydrologyScope
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from tests.hydrology_fixtures import (
    depression_heightmap as _depression_heightmap,
    hydro_master,
    hydro_world,
    lakes_hydrology,
)


def _world(**kwargs):
    kwargs.setdefault("hydrology", lakes_hydrology())
    return hydro_world(**kwargs)


class TestLakesAutoresolvePolicy(unittest.TestCase):

    def test_defaults_on(self):
        policy = lakes_autoresolve_policy(_world())
        self.assertTrue(policy.lakes_enabled)
        self.assertTrue(policy.autoresolve)

    def test_explicit_off(self):
        policy = lakes_autoresolve_policy(
            _world(hydrology={"enabled": True, "default_lakes": {"autoresolve": False}}),
        )
        self.assertFalse(policy.autoresolve)


class TestBasinFlood(unittest.TestCase):

    def test_flood_stays_within_prominence(self):
        hm = _depression_heightmap()
        interior = flood_basin_interior(
            hm,
            (5, 5),
            set(),
            prominence=50,
            max_radius=4,
        )
        self.assertIn((5, 5), interior)
        self.assertNotIn((0, 0), interior)
        self.assertGreater(len(interior), 1)


class TestProceduralLakes(unittest.TestCase):

    def test_autoresolve_carves_lake_role(self):
        hm = _depression_heightmap()
        master = hydro_master(scopes=frozenset({HydrologyScope.LAKES}))
        carved, bbox = autoresolve_lakes(_world(), hm, master, {})
        roles = {entry.role for entry in carved.values()}
        self.assertIn(HydrologyCellRole.LAKE, roles)
        self.assertTrue(bbox is not None)

    def test_skips_occupied_center(self):
        hm = _depression_heightmap()
        master = hydro_master(scopes=frozenset({HydrologyScope.LAKES}))
        occupied = {(5, 5): MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)}
        carved, _ = autoresolve_lakes(_world(), hm, master, occupied)
        self.assertEqual(carved, {})

    def test_service_lakes_scope_without_declare(self):
        hm = _depression_heightmap()
        master = hydro_master(scopes=frozenset({HydrologyScope.LAKES}))
        result = HydrologyGeneratorService().apply(_world(), [], hm, master=master)
        roles = {entry.role for entry in result.cell_index.by_cell.values()}
        self.assertIn(HydrologyCellRole.LAKE, roles)


if __name__ == "__main__":
    unittest.main()
