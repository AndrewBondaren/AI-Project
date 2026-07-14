"""MapGridRenderService pack gate — must not fall back to MapCell export."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.read.packReadServices import build_pack_read_services
from app.application.worldData.patchStoreService import PatchStoreService
from app.application.worldData.render.mapGridRenderService import MapGridRenderService
from app.dataModel.worldPack import WorldMapCellWire


class TestMapGridRenderServicePackGate(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "game.db")
        self.uid = "w-render-gate"
        paths = WorldPackPaths.from_db_parent(self.db_path, self.uid)
        writer = WorldPackWriter(paths)
        writer.write_world_map_tile(
            0, 0,
            [WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains")],
            cells_per_side=2,
        )
        writer.save_manifest()
        self.pack = build_pack_read_services(self.uid, PatchStoreService(), db_path=self.db_path)
        self.world = SimpleNamespace(world_uid=self.uid, map_cell_size_m=3000)

        self.map_cells = MagicMock()
        self.map_cells.uses_pack_read.return_value = True
        self.map_cells.pack_read_services.return_value = self.pack
        self.map_cells.get_all_for_read = AsyncMock(return_value=[])
        self.svc = MapGridRenderService(self.map_cells)

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    async def test_world_grid_pack_skips_map_cell_export(self) -> None:
        payload = await self.svc.render_world_grid(self.world)
        self.assertEqual(payload["read_path"], "pack")
        self.assertEqual(payload["read_mode"], "world_map_light")
        self.map_cells.get_all_for_read.assert_not_called()

    async def test_missing_location_terrain_skips_map_cell_export(self) -> None:
        payload = await self.svc.render_location_grid(self.world, "no-blob")
        self.assertEqual(payload["read_path"], "pack")
        self.assertEqual(payload["read_mode"], "location_terrain_missing")
        self.assertEqual(payload["levels"], {})
        self.map_cells.get_all_for_read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
