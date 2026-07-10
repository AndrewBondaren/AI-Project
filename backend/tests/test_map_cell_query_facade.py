"""MapCellQueryFacade tests with temp pack."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.worldData.mapCellQueryFacade import MapCellQueryFacade
from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.packReadServices import build_pack_read_services
from app.application.worldData.patchStoreService import PatchStoreService
from app.dataModel.worldPack import WorldMapCellWire
from app.dataModel.worldPack.layerPriority import MapLayerKind


def _world(**kwargs):
    defaults = {"world_uid": "w1", "map_cell_size_m": 3000}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestMapCellQueryFacade(unittest.IsolatedAsyncioTestCase):

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
        self.facade = self.services.gameplay
        self.debug = self.services.debug
        self.loading = self.services.loading

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    async def test_world_map_fallback_scene_volume(self):
        world = _world()
        views = await self.facade.get_scene_volume(world, 0, 0, 50, xy_radius=0)
        self.assertGreaterEqual(len(views), 1)
        self.assertEqual(views[0].source_layer, MapLayerKind.WORLD_MAP)
        self.assertEqual(views[0].system_terrain, "plains")

    async def test_sample_world_map_via_debug(self):
        world = _world()
        cells = self.debug.get_world_map_tile_sample_cells(world, 0, 0)
        self.assertGreaterEqual(len(cells), 1)
        self.assertEqual(cells[0].system_terrain, "plains")

    def test_loading_progress(self):
        snap = self.loading.get_loading_progress(_world())
        self.assertEqual(snap.world_map.world_map_tiles_ready, 1)


if __name__ == "__main__":
    unittest.main()
