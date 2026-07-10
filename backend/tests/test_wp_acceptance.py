"""WP acceptance unit tests — offline subset of WP-A6 / WP-A13."""

import unittest

from app.dataModel.worldPack import CellContribution, LayerSlice, MapLayerKind, merge_layers
from app.dataModel.worldPack.territoryVolume import TerritoryVolume


class TestWpAcceptance(unittest.TestCase):

    def test_wp_a6_patch_building_over_l2_wilderness(self):
        """WP-A6: settlement patch keeps building cells over L2 wilderness terrain."""
        layers = [
            LayerSlice(
                kind=MapLayerKind.WILDERNESS,
                cell=CellContribution(
                    x=100, y=200, z=0,
                    system_terrain="forest",
                    system_material="soil",
                ),
            ),
            LayerSlice(
                kind=MapLayerKind.PATCH,
                cell=CellContribution(
                    x=100, y=200, z=0,
                    system_building_element="wall",
                    is_structural=True,
                ),
            ),
        ]
        merged = merge_layers(100, 200, 0, layers)
        self.assertEqual(merged.system_building_element, "wall")
        self.assertEqual(merged.system_terrain, "forest")
        self.assertTrue(merged.is_structural)
        self.assertEqual(merged.field_sources["system_building_element"], MapLayerKind.PATCH)
        self.assertEqual(merged.field_sources["system_terrain"], MapLayerKind.WILDERNESS)

    def test_wp_a13_multi_location_per_tile_by_z(self):
        """WP-A13: same (x,y) different z — location vs wilderness layers."""
        wilderness = LayerSlice(
            kind=MapLayerKind.WILDERNESS,
            cell=CellContribution(x=5, y=5, z=-2, system_terrain="cave"),
        )
        loc_surface = LayerSlice(
            kind=MapLayerKind.LOCATION,
            cell=CellContribution(
                x=5, y=5, z=0,
                system_terrain="urban",
                location_uid="loc-a",
            ),
        )
        loc_upper = LayerSlice(
            kind=MapLayerKind.LOCATION,
            cell=CellContribution(
                x=5, y=5, z=3,
                system_terrain="urban",
                location_uid="loc-b",
            ),
        )
        surface = merge_layers(5, 5, 0, [wilderness, loc_surface])
        deep = merge_layers(5, 5, -2, [wilderness, loc_surface])
        upper = merge_layers(5, 5, 3, [wilderness, loc_upper])
        self.assertEqual(surface.location_uid, "loc-a")
        self.assertEqual(deep.system_terrain, "cave")
        self.assertEqual(upper.location_uid, "loc-b")

    def test_wp_a13_territory_volume_contains_z_band(self):
        vol = TerritoryVolume(x0=0, y0=0, z0=-5, x1=100, y1=100, z1=10)
        self.assertTrue(vol.contains(50, 50, 0))
        self.assertTrue(vol.contains(50, 50, -5))
        self.assertTrue(vol.contains(50, 50, 10))
        self.assertFalse(vol.contains(50, 50, 11))
        self.assertFalse(vol.contains(-1, 50, 0))


if __name__ == "__main__":
    unittest.main()
