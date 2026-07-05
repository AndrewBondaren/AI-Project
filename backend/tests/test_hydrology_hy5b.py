"""Unit tests for procedural lake autoresolve — D HY-5b."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.hydrology.hydrologyAutoresolvePolicy import (
    lakes_autoresolve_policy,
)
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.hydrology.proceduralLakeAutoresolve import (
    autoresolve_lakes,
    flood_basin_interior,
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
            "default_lakes": {
                "enabled": True,
                "autoresolve": True,
                "bands": {"min": 1, "max": 4},
            },
        },
        "map_cell_size_m": 3000,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _heightmap(surface_z: dict[tuple[int, int], int]) -> SurfaceHeightmap:
    xs = [gx for gx, _ in surface_z]
    ys = [gy for _, gy in surface_z]
    return SurfaceHeightmap(
        world_uid="test-world",
        bbox=GridBBox(min(xs), max(xs), min(ys), max(ys)),
        surface_z=dict(surface_z),
    )


def _depression_heightmap() -> SurfaceHeightmap:
    surface_z: dict[tuple[int, int], int] = {}
    for gx in range(0, 11):
        for gy in range(0, 11):
            ring = max(abs(gx - 5), abs(gy - 5))
            if ring == 0:
                surface_z[(gx, gy)] = 7950
            elif ring == 1:
                surface_z[(gx, gy)] = 8000
            elif ring <= 3:
                surface_z[(gx, gy)] = 8010
            else:
                surface_z[(gx, gy)] = 8050
    return _heightmap(surface_z)


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
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.LAKES}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
        )
        carved, bbox = autoresolve_lakes(_world(), hm, master, {})
        roles = {entry.role for entry in carved.values()}
        self.assertIn(HydrologyCellRole.LAKE, roles)
        self.assertTrue(bbox is not None)

    def test_skips_occupied_center(self):
        hm = _depression_heightmap()
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.LAKES}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
        )
        occupied = {(5, 5): MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)}
        carved, _ = autoresolve_lakes(_world(), hm, master, occupied)
        self.assertEqual(carved, {})

    def test_service_lakes_scope_without_declare(self):
        hm = _depression_heightmap()
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.LAKES}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
        )
        result = HydrologyGeneratorService().apply(_world(), [], hm, master=master)
        roles = {entry.role for entry in result.cell_index.by_cell.values()}
        self.assertIn(HydrologyCellRole.LAKE, roles)


if __name__ == "__main__":
    unittest.main()
