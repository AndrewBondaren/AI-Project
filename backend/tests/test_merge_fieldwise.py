"""Tests for field-wise merge and patch layer_kind."""

import unittest

from app.application.worldData.pack.read.patchCellContribution import map_cell_to_patch_contribution
from app.dataModel.worldPack import CellContribution, LayerSlice, MapLayerKind, merge_layers
from app.dataModel.worldPack.mapCellPatchLayerKind import MapCellPatchLayerKind
from app.db.models.mapCell import MapCell


class TestMergeFieldwise(unittest.TestCase):

    def test_patch_structure_over_wilderness_terrain(self):
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
        self.assertEqual(merged.system_terrain, "forest")
        self.assertEqual(merged.system_building_element, "wall")
        self.assertEqual(merged.source_layer, MapLayerKind.PATCH)
        self.assertEqual(merged.field_sources["system_terrain"], MapLayerKind.WILDERNESS)
        self.assertEqual(merged.field_sources["system_building_element"], MapLayerKind.PATCH)

    def test_climate_patch_layer_kind_fields_only(self):
        cell = MapCell(
            world_uid="w",
            x=3,
            y=4,
            z=0,
            layer_kind=MapCellPatchLayerKind.CLIMATE_DELTA.value,
            temperature_base=-5,
            rainfall=12,
        )
        contrib = map_cell_to_patch_contribution(cell)
        self.assertEqual(contrib.temperature_base, -5)
        self.assertIsNone(contrib.system_building_element)
        layers = [
            LayerSlice(
                kind=MapLayerKind.WILDERNESS,
                cell=CellContribution(x=3, y=4, z=0, system_terrain="plains"),
            ),
            LayerSlice(kind=MapLayerKind.PATCH, cell=contrib),
        ]
        merged = merge_layers(3, 4, 0, layers)
        self.assertEqual(merged.system_terrain, "plains")
        self.assertEqual(merged.temperature_base, -5)
        self.assertEqual(merged.rainfall, 12)

    def test_patch_read_merges_all_row_fields_regardless_of_layer_kind(self):
        """WP-FIX-DEBT-1: climate then ore on same cell — read must keep both."""
        cell = MapCell(
            world_uid="w",
            x=1,
            y=1,
            z=0,
            layer_kind=MapCellPatchLayerKind.ORE.value,
            temperature_base=-2,
            rainfall=8,
            system_material="iron",
        )
        contrib = map_cell_to_patch_contribution(cell)
        self.assertEqual(contrib.temperature_base, -2)
        self.assertEqual(contrib.rainfall, 8)
        self.assertEqual(contrib.system_material, "iron")


if __name__ == "__main__":
    unittest.main()
