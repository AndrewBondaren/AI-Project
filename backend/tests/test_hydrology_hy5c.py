"""Unit tests for procedural river autoresolve — D HY-5c."""

from tests.hydrology_fixtures import hydro_topology as _river_test_topology
import unittest

from app.application.worldData.generators.hydrology.riverNetworkAssembler import assemble_rivers
from app.application.worldData.generators.hydrology.autoresolve.proceduralRiverAutoresolve import (
    autoresolve_river_segments,
)
from app.application.worldData.generators.hydrology.rivers.riverNetworkPlanner import (
    plan_descent_path,
)
from app.application.worldData.generators.hydrology.geom.smoothRiverPolyline import (
    turn_angle_deg,
)
from app.application.worldData.generators.hydrology.types import HydrologyScope
from app.dataModel.hydrology.enums.hydrologyCellRole import HydrologyCellRole
from app.dataModel.hydrology.mapCellHydrology import MapCellHydrology
from tests.hydrology_fixtures import (
    heightmap_from_z as _heightmap,
    hydro_master,
    hydro_world,
    rivers_hydrology,
)


def _world(**kwargs):
    kwargs.setdefault("hydrology", rivers_hydrology())
    return hydro_world(**kwargs)


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
        path = plan_descent_path(hm, (3, 5), occupied, topology=_river_test_topology(hm))
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
        master = hydro_master(scopes=frozenset({HydrologyScope.RIVERS}))
        segments = autoresolve_river_segments(_world(), hm, master, occupied, topology=_river_test_topology(hm))
        self.assertGreater(len(segments), 0)
        self.assertFalse(segments[0].declared)

    def test_assemble_rivers_autoresolve_with_occupied_ocean(self):
        surface_z = {(gx, gy): 10 for gx in range(8) for gy in range(8)}
        for gy in range(1, 8):
            surface_z[(4, gy)] = 10 + gy * 6
        hm = _heightmap(surface_z)
        occupied = {
            (gx, 0): MapCellHydrology(role=HydrologyCellRole.OPEN_OCEAN)
            for gx in range(8)
        }
        master = hydro_master(scopes=frozenset({HydrologyScope.RIVERS}))
        result = assemble_rivers(
            _world(),
            hm,
            master,
            occupied=occupied,
            locations=[],
            topology=_river_test_topology(hm),
        )
        roles = {entry.role for entry in result.by_cell.values()}
        self.assertIn(HydrologyCellRole.RIVER_BED, roles)
        self.assertGreater(len(result.segments), 0)


if __name__ == "__main__":
    unittest.main()
