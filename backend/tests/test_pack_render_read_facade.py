"""PackRenderReadFacade — L0 + location_terrain loads for ASCII render."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.read.packReadServices import build_pack_read_services
from app.application.worldData.patchStoreService import PatchStoreService
from app.application.worldData.render.renderPayloads import LEVEL_SURFACE
from app.dataModel.worldPack import (
    FineTerrainChunkWire,
    FineTerrainColumnWire,
    FineTerrainZRun,
    TerritoryVolume,
    WorldMapCellWire,
)
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire


def _world(uid: str = "w-render-read", **kwargs):
    defaults = {"world_uid": uid, "map_cell_size_m": 3000}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestPackRenderReadFacade(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmpdir.name) / "game.db")
        self.uid = "w-render-read"
        self.paths = WorldPackPaths.from_db_parent(self.db_path, self.uid)
        self.writer = WorldPackWriter(self.paths)
        self.world = _world(self.uid)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _services(self):
        return build_pack_read_services(self.uid, PatchStoreService(), db_path=self.db_path)

    def test_try_world_map_source_none_without_pack(self) -> None:
        facade = self._services().render
        self.assertIsNone(facade.try_world_map_source(self.world))

    def test_try_world_map_source_with_tiles_and_pins(self) -> None:
        self.writer.write_world_map_tile(
            0, 0,
            [WorldMapCellWire(tx=0, ty=0, surface_z=1, system_terrain="plains")],
            cells_per_side=2,
        )
        self.writer.write_locations_index(
            LocationsIndexWire(
                locations=[
                    LocationsIndexPin(location_uid="loc-a", map_x=100, map_y=200),
                ],
            ),
        )
        self.writer.save_manifest()
        src = self._services().render.try_world_map_source(self.world)
        self.assertIsNotNone(src)
        assert src is not None
        self.assertEqual(len(src.tiles), 1)
        self.assertEqual(src.tiles[0].gx, 0)
        self.assertEqual(len(src.pins.locations), 1)
        self.assertEqual(src.tile_size_m, 3000)

    def test_has_and_try_location_terrain(self) -> None:
        chunk = FineTerrainChunkWire(
            cx=0,
            cy=0,
            chunk_columns=8,
            columns=[
                FineTerrainColumnWire(
                    lx=0,
                    ly=0,
                    runs=[FineTerrainZRun(z0=0, z1=2, system_terrain="plains")],
                ),
            ],
        )
        vol = TerritoryVolume(x0=10, y0=20, z0=0, x1=20, y1=30, z1=5)
        # Manifest-only without blob should be false — write blob via writer.
        self.writer.write_location_terrain("loc-a", chunk, territory_volume=vol)
        self.writer.save_manifest()
        facade = self._services().render
        self.assertTrue(facade.has_location_terrain(self.world, "loc-a"))
        self.assertFalse(facade.has_location_terrain(self.world, "missing"))
        src = facade.try_location_terrain(self.world, "loc-a")
        self.assertIsNotNone(src)
        assert src is not None
        self.assertEqual(src.location_uid, "loc-a")
        self.assertEqual(src.volume.x0, 10)
        self.assertEqual(src.chunk.columns[0].runs[0].system_terrain, "plains")
        self.assertEqual(facade.location_uids_with_terrain(self.world), ["loc-a"])
        # Surface key constant stays stable for consumers.
        self.assertEqual(LEVEL_SURFACE, "surface")


if __name__ == "__main__":
    unittest.main()
