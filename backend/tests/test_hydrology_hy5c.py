"""Unit tests for procedural river autoresolve — D HY-5c."""

import unittest
from types import SimpleNamespace

from app.application.worldData.generators.climate.climatePoleField import GridBBox
from app.application.worldData.generators.terrain.hydrology.hydrologyGeneratorService import (
    HydrologyGeneratorService,
)
from app.application.worldData.generators.terrain.hydrology.proceduralRiverAutoresolve import (
    autoresolve_river_segments,
)
from app.application.worldData.generators.terrain.hydrology.riverNetworkPlanner import (
    plan_descent_path,
)
from app.application.worldData.generators.terrain.hydrology.smoothRiverPolyline import (
    turn_angle_deg,
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
            "default_rivers": {"enabled": True, "autoresolve": True},
        },
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


class TestSmoothRiverPolyline(unittest.TestCase):

    def test_right_angle_is_90(self):
        self.assertAlmostEqual(turn_angle_deg((0, 0), (1, 0), (1, 1)), 90.0)


class TestRiverPlanner(unittest.TestCase):

    def test_descent_reaches_water_mouth(self):
        surface_z = {(gx, gy): 10 for gx in range(6) for gy in range(6)}
        for gy in range(1, 6):
            surface_z[(3, gy)] = 10 + gy * 5
        hm = _heightmap(surface_z)
        occupied = {
            (gx, 0): MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)
            for gx in range(6)
        }
        path = plan_descent_path(hm, (3, 5), occupied)
        self.assertGreaterEqual(len(path), 2)
        self.assertEqual(path[-1][1], 0)


class TestRiverAutoresolve(unittest.TestCase):

    def test_autoresolve_segments_from_peak_to_ocean(self):
        surface_z = {(gx, gy): 10 for gx in range(8) for gy in range(8)}
        for gy in range(1, 8):
            surface_z[(4, gy)] = 10 + gy * 6
        hm = _heightmap(surface_z)
        occupied = {
            (gx, 0): MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)
            for gx in range(8)
        }
        master = HydrologyMasterInput(
            world_uid="test-world",
            hydrology_enabled=True,
            scopes=frozenset({HydrologyScope.RIVERS}),
            connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
        )
        segments = autoresolve_river_segments(_world(), hm, master, occupied)
        self.assertGreater(len(segments), 0)
        self.assertFalse(segments[0].declared)

    def test_service_carves_autoresolve_with_ocean_scope(self):
        surface_z = {(gx, gy): 10 for gx in range(8) for gy in range(8)}
        for gy in range(1, 8):
            surface_z[(4, gy)] = 10 + gy * 6
        hm = _heightmap(surface_z)
        result = HydrologyGeneratorService().apply(
            _world(),
            [],
            hm,
            master=HydrologyMasterInput(
                world_uid="test-world",
                hydrology_enabled=True,
                scopes=frozenset({HydrologyScope.COASTAL_SEA, HydrologyScope.OPEN_OCEAN, HydrologyScope.RIVERS}),
                connection_graph=LoadedConnectionGraph(nodes=[], edges=[]),
            ),
        )
        roles = {entry.role for entry in result.cell_index.by_cell.values()}
        self.assertIn(HydrologyCellRole.RIVER_BED, roles)
        self.assertGreater(len(result.river_segments), 0)


if __name__ == "__main__":
    unittest.main()
