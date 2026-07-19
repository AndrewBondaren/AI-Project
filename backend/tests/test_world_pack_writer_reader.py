"""WorldPackWriter/Reader integration on temp dir."""

import tempfile
import unittest
from pathlib import Path

from app.application.worldData.pack import WorldPackPaths, WorldPackReader, WorldPackWriter
from app.dataModel.worldPack import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun, TerritoryVolume, WorldMapCellWire


class TestWorldPackWriterReader(unittest.TestCase):

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.paths = WorldPackPaths.from_worlds_root(Path(self._tmpdir.name), "world-test")
        self.writer = WorldPackWriter(self.paths)
        self.reader = WorldPackReader(self.paths)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_world_map_roundtrip(self):
        cells = [WorldMapCellWire(tx=0, ty=0, surface_z=42)]
        h1 = self.writer.write_world_map_tile(0, 0, cells, cells_per_side=32)
        self.writer.save_manifest()
        side, restored = self.reader.read_world_map_tile(0, 0)
        self.assertEqual(side, 32)
        self.assertEqual(restored[0].surface_z, 42)
        manifest = self.reader.load_manifest()
        tile = manifest.tile_entry(0, 0)
        self.assertIsNotNone(tile)
        assert tile is not None
        self.assertEqual(tile.world_map_hash, h1)

    def test_wilderness_chunk_manifest_commit(self):
        chunk = FineTerrainChunkWire(
            cx=0,
            cy=0,
            chunk_columns=32,
            columns=[
                FineTerrainColumnWire(lx=1, ly=2, runs=[FineTerrainZRun(z0=-1, z1=0, system_terrain="forest", system_material="earth")]),
            ],
        )
        h1 = self.writer.write_wilderness_chunk(1, 2, chunk)
        self.writer.save_manifest()
        restored = self.reader.read_wilderness_chunk(1, 2, 0, 0)
        self.assertEqual(restored.columns[0].lx, 1)
        self.assertEqual(restored.columns[0].runs[0].system_terrain, "forest")
        manifest = self.reader.load_manifest()
        ref = manifest.chunk_ref(1, 2, 0, 0)
        self.assertIsNotNone(ref)
        assert ref is not None
        self.assertEqual(ref.content_hash, h1)

    def test_crash_mid_chunk_no_manifest_entry(self):
        chunk = FineTerrainChunkWire(cx=1, cy=1, chunk_columns=32, columns=[])
        blob_path = self.paths.wilderness_chunk_path(3, 3, 1, 1)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        blob_path.with_suffix(blob_path.suffix + ".tmp").write_bytes(b"partial")
        self.assertFalse(self.reader.chunk_exists(3, 3, 1, 1))
        manifest = self.writer.manifest
        self.assertIsNone(manifest.chunk_ref(3, 3, 1, 1))

    def test_location_terrain_write(self):
        chunk = FineTerrainChunkWire(cx=0, cy=0, chunk_columns=8, columns=[])
        vol = TerritoryVolume(x0=0, y0=0, z0=-2, x1=10, y1=10, z1=0)
        self.writer.write_location_terrain("loc-a", chunk, territory_volume=vol)
        self.writer.save_manifest()
        loc = self.reader.manifest.location_entry("loc-a")
        self.assertIsNotNone(loc)
        restored = self.reader.read_location_terrain("loc-a")
        self.assertEqual(restored.chunk_columns, 8)

    def test_manifest_cache_reloads_when_disk_stamp_changes(self):
        """Stale in-memory manifest must not hide tiles written by a later bake."""
        self.writer.write_world_map_tile(
            0, 0, [WorldMapCellWire(tx=0, ty=0, surface_z=1)], cells_per_side=32,
        )
        self.writer.save_manifest()
        first = self.reader.manifest
        self.assertEqual(len(first.tiles), 1)

        # Second writer simulates full bake expanding the pack (same process as reader).
        writer2 = WorldPackWriter(self.paths)
        writer2.write_world_map_tile(
            0, 0, [WorldMapCellWire(tx=0, ty=0, surface_z=1)], cells_per_side=32,
        )
        writer2.write_world_map_tile(
            1, 0, [WorldMapCellWire(tx=0, ty=0, surface_z=2)], cells_per_side=32,
        )
        writer2.save_manifest()

        second = self.reader.manifest
        self.assertEqual(len(second.tiles), 2)
        self.assertIsNotNone(second.tile_entry(1, 0))

    def test_invalidate_manifest_forces_reload(self):
        self.writer.write_world_map_tile(
            0, 0, [WorldMapCellWire(tx=0, ty=0, surface_z=1)], cells_per_side=32,
        )
        self.writer.save_manifest()
        self.assertEqual(len(self.reader.manifest.tiles), 1)
        self.reader.invalidate_manifest()
        # Corrupt stamp simulation: rewrite without going through property
        writer2 = WorldPackWriter(self.paths)
        writer2.write_world_map_tile(
            0, 0, [WorldMapCellWire(tx=0, ty=0, surface_z=1)], cells_per_side=32,
        )
        writer2.write_world_map_tile(
            -1, -1, [WorldMapCellWire(tx=0, ty=0, surface_z=3)], cells_per_side=32,
        )
        writer2.save_manifest()
        self.assertEqual(len(self.reader.manifest.tiles), 2)


if __name__ == "__main__":
    unittest.main()
