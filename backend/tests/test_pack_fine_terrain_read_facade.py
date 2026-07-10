"""Pack fine-terrain read debug facade."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.packReadServices import build_pack_read_services
from app.application.worldData.patchStoreService import PatchStoreService
from app.dataModel.worldPack import FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun, WorldMapCellWire


def _world(**kwargs):
    defaults = {"world_uid": "w-fine-read", "map_cell_size_m": 3000}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestPackFineTerrainReadFacade(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "game.db")
        self.paths = WorldPackPaths.from_db_parent(self.db_path, "w-fine-read")
        writer = WorldPackWriter(self.paths)
        chunk = FineTerrainChunkWire(
            cx=0,
            cy=0,
            chunk_columns=32,
            columns=[
                FineTerrainColumnWire(
                    lx=1,
                    ly=2,
                    runs=[FineTerrainZRun(z0=-1, z1=0, system_terrain="forest", system_material="earth")],
                ),
            ],
        )
        writer.write_world_map_tile(
            12, 12, [WorldMapCellWire(tx=0, ty=0, surface_z=10)], cells_per_side=32,
        )
        self.chunk_hash = writer.write_wilderness_chunk(12, 12, chunk, refine_role="scene")
        writer.save_manifest()
        self.services = build_pack_read_services(
            "w-fine-read", PatchStoreService(), db_path=self.db_path,
        )
        self.facade = self.services.fine_terrain_read
        self.world = _world()

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_read_tile_lists_chunk(self) -> None:
        payload = self.facade.read_tile(self.world, 12, 12)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["read_mode"], "tile")
        self.assertEqual(payload["wilderness_refine_status"], "partial")
        self.assertEqual(len(payload["chunks"]), 1)
        self.assertEqual(payload["chunks"][0]["content_hash"], self.chunk_hash)
        self.assertTrue(payload["chunks"][0]["blob_on_disk"])

    def test_read_wilderness_chunk_decodes_columns(self) -> None:
        payload = self.facade.read_wilderness_chunk(self.world, 12, 12, 0, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["read_mode"], "wilderness_chunk")
        self.assertTrue(payload["blob_on_disk"])
        self.assertEqual(payload["column_count"], 1)
        self.assertEqual(payload["sample_columns"][0]["runs"][0]["system_terrain"], "forest")

    async def test_read_merged_cell_reads_fine_layer(self) -> None:
        tile_m = self.world.map_cell_size_m
        x = 12 * tile_m + 1
        y = 12 * tile_m + 2
        payload = await self.facade.read_merged_cell(self.world, x, y, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["read_mode"], "merged_cell")
        self.assertTrue(payload["has_data"])
        self.assertEqual(payload["system_terrain"], "forest")
        self.assertIn("system_terrain", payload["field_sources"])


if __name__ == "__main__":
    unittest.main()
