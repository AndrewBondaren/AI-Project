"""REVIEW-1: pack root resolution for presence and I/O."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.worldData.mapCellReadService import MapCellReadService
from app.application.worldData.pack.packPresence import has_pack
from app.application.worldData.pack.packReadServices import build_pack_read_services
from app.application.worldData.pack.worldPackPaths import WorldPackPaths, resolve_pack_root
from app.application.worldData.pack.worldPackWriter import WorldPackWriter
from app.application.worldData.patchStoreService import PatchStoreService
from app.dataModel.worldPack import WorldMapCellWire


def _world(**kwargs):
    defaults = {"world_uid": "w1", "map_cell_size_m": 3000}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestPackRootResolution(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tmpdir.name)
        self.db_path = str(self.root / "game.db")
        self.default_paths = WorldPackPaths.from_db_parent(self.db_path, "w1")

    async def asyncTearDown(self) -> None:
        self._tmpdir.cleanup()

    def _write_manifest(self, pack_root: Path) -> None:
        pack_root.mkdir(parents=True, exist_ok=True)
        paths = WorldPackPaths.from_pack_root(pack_root, "w1")
        writer = WorldPackWriter(paths)
        writer.write_l0_world_map(
            0, 0,
            [WorldMapCellWire(tx=0, ty=0, surface_z=10, system_terrain="plains")],
            cells_per_side=32,
        )
        writer.save_manifest()

    async def test_custom_terrain_pack_path_used_for_read(self):
        custom_root = self.root / "fixtures" / "packs" / "w1"
        self._write_manifest(custom_root)
        world = _world(terrain_pack_path="fixtures/packs/w1")

        resolved = resolve_pack_root(world, db_path=self.db_path, world_uid="w1")
        self.assertEqual(resolved, custom_root.resolve())

        services = build_pack_read_services("w1", PatchStoreService(), db_path=self.db_path)
        read = MapCellReadService(services)
        self.assertTrue(read.has_pack_for(world))
        cells = services.debug.get_l0_tile_sample_cells(world, 0, 0)
        self.assertGreaterEqual(len(cells), 1)
        self.assertEqual(cells[0].z, 10)

    def test_has_pack_false_when_only_default_missing_custom(self):
        world = _world(terrain_pack_path="fixtures/packs/missing")
        self.assertFalse(has_pack(world, self.default_paths, db_path=self.db_path))

    def test_default_layout_when_no_terrain_pack_path(self):
        self._write_manifest(self.default_paths.root)
        world = _world()
        self.assertTrue(has_pack(world, self.default_paths, db_path=self.db_path))
        self.assertEqual(
            resolve_pack_root(world, db_path=self.db_path, world_uid="w1"),
            self.default_paths.root,
        )


if __name__ == "__main__":
    unittest.main()
