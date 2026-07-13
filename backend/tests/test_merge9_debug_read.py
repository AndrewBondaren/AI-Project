"""MERGE-9: debug read path routes through pack facades."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.worldData.mapCellReadService import MapCellReadService
from app.application.worldData.mapCellService import MapCellService
from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.read.packReadServices import build_pack_read_services
from app.application.worldData.patchStoreService import PatchStoreService
from app.dataModel.worldPack import WorldMapCellWire


def _world(**kwargs):
    defaults = {"world_uid": "w1", "map_cell_size_m": 3000}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestMerge9DebugRead(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "game.db")
        self.paths = WorldPackPaths.from_db_parent(self.db_path, "w1")
        writer = WorldPackWriter(self.paths)
        writer.write_world_map_tile(
            0, 0,
            [WorldMapCellWire(tx=0, ty=0, surface_z=50, system_terrain="plains")],
            cells_per_side=32,
        )
        writer.save_manifest()
        self.services = build_pack_read_services(
            "w1", PatchStoreService(), db_path=self.db_path,
        )
        self.read = MapCellReadService(self.services)
        self.world = _world()

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_facade_world_map_surface_cells(self):
        cells = self.services.debug.get_world_map_surface_cells(self.world)
        self.assertGreaterEqual(len(cells), 1)
        self.assertEqual(cells[0].system_terrain, "plains")

    async def test_map_cell_service_get_all_for_read_uses_facade(self):
        svc = MapCellService(None, read_service_factory=lambda _uid: self.read)
        cells = await svc.get_all_for_read(self.world)
        self.assertTrue(svc.uses_pack_read(self.world))
        self.assertGreaterEqual(len(cells), 1)
        self.assertEqual(cells[0].system_terrain, "plains")

    async def test_debug_export_merges_patch_over_l0(self):
        from unittest.mock import AsyncMock, MagicMock

        from app.db.models.mapCell import MapCell

        world_map_cells = self.services.debug.get_world_map_surface_cells(self.world)
        self.assertGreaterEqual(len(world_map_cells), 1)
        anchor = world_map_cells[0]
        patch_cell = MapCell(
            world_uid="w1",
            x=anchor.x,
            y=anchor.y,
            z=anchor.z,
            system_terrain="mountain",
            layer_kind="terrain_delta",
        )
        repo = MagicMock()
        repo.get_by_world = AsyncMock(return_value=[patch_cell])
        services = build_pack_read_services(
            "w1", PatchStoreService(repo), db_path=self.db_path,
        )
        merged = await services.debug.get_debug_export_cells(self.world)
        by_key = {(c.x, c.y, c.z): c for c in merged}
        cell = by_key[(anchor.x, anchor.y, anchor.z)]
        self.assertEqual(cell.system_terrain, "mountain")
        self.assertEqual(len(merged), len(world_map_cells))

    async def test_column_has_merged_data(self):
        cells = self.services.debug.get_world_map_surface_cells(self.world)
        self.assertGreaterEqual(len(cells), 1)
        has = await self.services.debug.column_has_merged_data(self.world, cells[0].x, cells[0].y)
        self.assertTrue(has)


if __name__ == "__main__":
    unittest.main()
