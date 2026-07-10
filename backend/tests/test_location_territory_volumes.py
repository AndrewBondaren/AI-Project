"""DEBT-6: settlement footprint territory volumes."""

import unittest
from types import SimpleNamespace

from app.application.worldData.pack.locationTerritoryVolumes import (
    settlement_footprint_side_m,
    territory_volume_for_location,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_side_m,
)


def _world(**kwargs):
    defaults = {"world_uid": "w1", "map_cell_size_m": 3000, "map_subsurface_depth": 10}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _location(**kwargs):
    defaults = {
        "location_uid": "loc-1",
        "system_location_type": "landmark",
        "map_x": 100,
        "map_y": 200,
        "map_z": 50,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestLocationTerritoryVolumes(unittest.TestCase):

    def test_settlement_uses_footprint_side_from_assembler(self):
        world = _world()
        loc = _location(system_location_type="settlement", system_city_size="hamlet")
        side = settlement_footprint_side_m(world, loc)
        self.assertEqual(side, footprint_side_m(world, "hamlet"))
        vol = territory_volume_for_location(world, loc)
        assert vol is not None
        self.assertEqual(vol.x0, 100)
        self.assertEqual(vol.y0, 200)
        self.assertEqual(vol.x1, 100 + side - 1)
        self.assertEqual(vol.y1, 200 + side - 1)
        self.assertEqual(vol.z1, 50 + 32)

    def test_pin_location_uses_policy_box(self):
        world = _world()
        loc = _location(system_location_type="landmark")
        vol = territory_volume_for_location(world, loc)
        assert vol is not None
        self.assertEqual(vol.x0, 95)
        self.assertEqual(vol.x1, 105)
        self.assertEqual(vol.y0, 195)
        self.assertEqual(vol.y1, 205)
        self.assertEqual(vol.z1, 52)


if __name__ == "__main__":
    unittest.main()
