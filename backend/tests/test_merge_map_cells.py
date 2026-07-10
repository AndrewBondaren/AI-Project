"""Tests for WP-20 merge_layers."""

import unittest

from app.dataModel.worldPack import CellContribution, LayerSlice, MapLayerKind, merge_layers


class TestMergeMapCells(unittest.TestCase):

    def test_patch_wins_over_wilderness(self):
        layers = [
            LayerSlice(
                kind=MapLayerKind.WILDERNESS,
                cell=CellContribution(x=1, y=2, z=0, system_terrain="forest"),
            ),
            LayerSlice(
                kind=MapLayerKind.PATCH,
                cell=CellContribution(x=1, y=2, z=0, system_building_element="wall"),
            ),
        ]
        merged = merge_layers(1, 2, 0, layers)
        self.assertEqual(merged.source_layer, MapLayerKind.PATCH)
        self.assertEqual(merged.system_building_element, "wall")

    def test_location_over_wilderness_by_z(self):
        layers = [
            LayerSlice(
                kind=MapLayerKind.WILDERNESS,
                cell=CellContribution(x=5, y=5, z=-3, system_terrain="cave"),
            ),
            LayerSlice(
                kind=MapLayerKind.LOCATION,
                cell=CellContribution(x=5, y=5, z=0, system_terrain="urban"),
            ),
        ]
        merged_surface = merge_layers(5, 5, 0, layers)
        merged_under = merge_layers(5, 5, -3, layers)
        self.assertEqual(merged_surface.source_layer, MapLayerKind.LOCATION)
        self.assertEqual(merged_surface.system_terrain, "urban")
        self.assertEqual(merged_under.source_layer, MapLayerKind.WILDERNESS)

    def test_world_map_fallback_when_no_fine(self):
        layers = [
            LayerSlice(
                kind=MapLayerKind.WORLD_MAP,
                cell=CellContribution(x=0, y=0, z=0, system_terrain="plains"),
            ),
        ]
        merged = merge_layers(0, 0, 0, layers)
        self.assertEqual(merged.source_layer, MapLayerKind.WORLD_MAP)

    def test_empty_when_no_layer_has_cell(self):
        merged = merge_layers(9, 9, 0, [])
        self.assertIsNone(merged.source_layer)


if __name__ == "__main__":
    unittest.main()
