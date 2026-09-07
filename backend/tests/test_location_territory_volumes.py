"""DEBT-6: settlement footprint territory volumes."""

import unittest
from types import SimpleNamespace

from app.application.worldData.pack.read.locationTerritoryVolumes import (
    settlement_footprint_side_fine,
    territory_volume_for_location,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.footprint import (
    footprint_side_fine,
)
from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy


def _world(**kwargs):
    defaults = {"world_uid": "w1", "fine_cells_per_map_cell": 3000, "map_subsurface_depth": 10}
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
        side = settlement_footprint_side_fine(world, loc)
        self.assertEqual(side, footprint_side_fine(world, "hamlet"))
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
        half = TerritoryVolumePolicy.pin_half_extent_xy()
        self.assertEqual(vol.x0, 100 - half)
        self.assertEqual(vol.x1, 100 + half)
        self.assertEqual(vol.y0, 200 - half)
        self.assertEqual(vol.y1, 200 + half)
        self.assertEqual(vol.z1, 52)


if __name__ == "__main__":
    unittest.main()
