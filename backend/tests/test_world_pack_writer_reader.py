"""WorldPackWriter/Reader integration on temp dir."""

import tempfile
import unittest
from pathlib import Path

from app.application.worldData.pack import WorldPackPaths, WorldPackReader, WorldPackWriter
from app.dataModel.worldPack import L2ChunkWire, L2ColumnWire, L2ZRun, TerritoryVolume, WorldMapCellWire


class TestWorldPackWriterReader(unittest.TestCase):

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.paths = WorldPackPaths.from_worlds_root(Path(self._tmpdir.name), "world-test")
        self.writer = WorldPackWriter(self.paths)
        self.reader = WorldPackReader(self.paths)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_l0_roundtrip(self):
        cells = [WorldMapCellWire(tx=0, ty=0, surface_z=42)]
        h1 = self.writer.write_l0_world_map(0, 0, cells, cells_per_side=32)
        self.writer.save_manifest()
        side, restored = self.reader.read_l0_tile(0, 0)
        self.assertEqual(side, 32)
        self.assertEqual(restored[0].surface_z, 42)
        manifest = self.reader.load_manifest()
        tile = manifest.tile_entry(0, 0)
        self.assertIsNotNone(tile)
        assert tile is not None
        self.assertEqual(tile.world_map_hash, h1)

    def test_l2_chunk_manifest_commit(self):
        chunk = L2ChunkWire(
            cx=0,
            cy=0,
            chunk_columns=32,
            columns=[
                L2ColumnWire(lx=1, ly=2, runs=[L2ZRun(z0=-1, z1=0, system_terrain="forest", system_material="earth")]),
            ],
        )
        h1 = self.writer.write_l2_wilderness_chunk(1, 2, chunk)
        self.writer.save_manifest()
        restored = self.reader.read_l2_chunk(1, 2, 0, 0)
        self.assertEqual(restored.columns[0].lx, 1)
        self.assertEqual(restored.columns[0].runs[0].system_terrain, "forest")
        manifest = self.reader.load_manifest()
        ref = manifest.chunk_ref(1, 2, 0, 0)
        self.assertIsNotNone(ref)
        assert ref is not None
        self.assertEqual(ref.content_hash, h1)

    def test_crash_mid_chunk_no_manifest_entry(self):
        chunk = L2ChunkWire(cx=1, cy=1, chunk_columns=32, columns=[])
        blob_path = self.paths.l2_chunk_path(3, 3, 1, 1)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.with_suffix(blob_path.suffix + ".tmp").write_bytes(b"partial")
        self.assertFalse(self.reader.chunk_exists(3, 3, 1, 1))
        manifest = self.writer.manifest
        self.assertIsNone(manifest.chunk_ref(3, 3, 1, 1))

    def test_location_l2_write(self):
        chunk = L2ChunkWire(cx=0, cy=0, chunk_columns=8, columns=[])
        vol = TerritoryVolume(x0=0, y0=0, z0=-2, x1=10, y1=10, z1=0)
        self.writer.write_location_l2("loc-a", chunk, territory_volume=vol)
        self.writer.save_manifest()
        loc = self.reader.manifest.location_entry("loc-a")
        self.assertIsNotNone(loc)
        restored = self.reader.read_location_l2("loc-a")
        self.assertEqual(restored.chunk_columns, 8)


if __name__ == "__main__":
    unittest.main()
