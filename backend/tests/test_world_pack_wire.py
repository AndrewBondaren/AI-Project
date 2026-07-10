"""Golden tests for World Pack wire POJOs."""

import json
import unittest

from app.dataModel.worldPack import (
    CellContribution,
    LayerSlice,
    MapLayerKind,
    TerritoryVolume,
    WorldMapCellWire,
    WorldPackManifest,
    inside_location_volume,
    merge_layers,
    resolve_world_map_cells_per_tile,
)
from app.dataModel.worldPack.hydrologyMaskWire import L0HydrologyRole


class TestWorldMapCellsPerTile(unittest.TestCase):

    def test_wp10_examples(self):
        self.assertEqual(resolve_world_map_cells_per_tile(3000), 32)
        self.assertEqual(resolve_world_map_cells_per_tile(1000), 48)
        self.assertEqual(resolve_world_map_cells_per_tile(6000), 16)
        self.assertEqual(resolve_world_map_cells_per_tile(4000), 24)

    def test_override_clamped(self):
        self.assertEqual(resolve_world_map_cells_per_tile(3000, override=4), 8)
        self.assertEqual(resolve_world_map_cells_per_tile(3000, override=99), 48)


class TestWorldPackWire(unittest.TestCase):

    def test_manifest_roundtrip_json(self):
        manifest = WorldPackManifest(
            world_uid="w-test",
            world_map_cells_per_tile=32,
            tiles=[{"gx": 0, "gy": 0, "l2_status": "partial", "chunks": [{"cx": 0, "cy": 0}]}],
            locations_l2=[
                {
                    "location_uid": "loc-1",
                    "territory_volume": {"x0": 0, "y0": 0, "z0": -2, "x1": 10, "y1": 10, "z1": 0},
                },
            ],
        )
        raw = json.loads(manifest.model_dump_json())
        restored = WorldPackManifest.model_validate(raw)
        self.assertEqual(restored.world_uid, "w-test")
        self.assertEqual(len(restored.tiles[0].chunks), 1)
        self.assertTrue(restored.location_entry("loc-1") is not None)

    def test_world_map_cell_wire(self):
        cell = WorldMapCellWire(tx=1, ty=2, surface_z=100, hydrology_role="river", hydrology_width=3)
        self.assertEqual(cell.hydrology_role, L0HydrologyRole.RIVER)
        self.assertEqual(cell.hydrology.width, 3)


class TestTerritoryVolume(unittest.TestCase):

    def test_normalize_inverted_bounds(self):
        vol = TerritoryVolume(x0=10, y0=10, z0=0, x1=0, y1=0, z1=-5)
        self.assertEqual((vol.x0, vol.x1), (0, 10))
        self.assertTrue(vol.contains(5, 5, -2))
        self.assertFalse(vol.contains(5, 5, 5))

    def test_inside_location_volume(self):
        volumes = [TerritoryVolume(x0=0, y0=0, z0=0, x1=5, y1=5, z1=0)]
        self.assertTrue(inside_location_volume(2, 2, 0, volumes))
        self.assertFalse(inside_location_volume(2, 2, -1, volumes))


if __name__ == "__main__":
    unittest.main()
