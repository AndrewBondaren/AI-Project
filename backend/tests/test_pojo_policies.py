"""POJO policies for scene volume, path heading, location footprint, territory."""

import unittest

from app.dataModel.locations.locationFootprintPolicy import (
    named_location_uses_settlement_meter_footprint,
    uses_settlement_meter_footprint,
)
from app.dataModel.terrain.sceneVolumePolicy import SceneVolumePolicy
from app.dataModel.worldPack.pathHeadingPolicy import PathHeadingPolicy
from app.dataModel.worldPack.territoryVolumePolicy import TerritoryVolumePolicy


class TestPojoPolicies(unittest.TestCase):

    def test_scene_volume_policy_defaults(self):
        policy = SceneVolumePolicy.canonical_defaults()
        self.assertEqual(policy.scene_xy_radius, 20)
        self.assertEqual(policy.scene_z_above, 6)

    def test_territory_pin_half_links_scene_volume(self):
        self.assertEqual(
            TerritoryVolumePolicy.pin_half_extent_xy(),
            SceneVolumePolicy.canonical_defaults().scene_xy_radius,
        )

    def test_path_heading_policy_corridor_width(self):
        policy = PathHeadingPolicy.canonical_defaults()
        self.assertEqual(policy.position_history_max, 5)
        self.assertEqual(policy.corridor_half_width_m(32), 32.0)

    def test_settlement_footprint_from_registry(self):
        self.assertTrue(
            uses_settlement_meter_footprint(
                system_location_type="settlement",
                system_city_size="hamlet",
            )
        )
        self.assertTrue(uses_settlement_meter_footprint(system_location_type="district"))
        self.assertFalse(uses_settlement_meter_footprint(system_location_type="landmark"))

    def test_named_location_footprint_helper(self):
        from types import SimpleNamespace

        loc = SimpleNamespace(
            system_location_type="settlement",
            system_location_subtype=None,
            system_city_size="village",
        )
        self.assertTrue(named_location_uses_settlement_meter_footprint(loc))


if __name__ == "__main__":
    unittest.main()
