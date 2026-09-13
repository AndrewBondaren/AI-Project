"""PackRenderReadFacade — L0 + location_terrain loads for ASCII render."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.read.packReadServices import build_pack_read_services
from app.application.worldData.patchStoreService import PatchStoreService
from app.application.worldData.render.packMapGridRender import PackMapGridRender
from app.application.worldData.render.renderPayloads import LEVEL_SURFACE, city_level_key
from app.dataModel.spatial.facing import Facing
from app.dataModel.worldPack import (
    AreaSlotWire,
    AreaStructureWire,
    DistrictStructureWire,
    FineTerrainChunkWire,
    FineTerrainColumnWire,
    FineTerrainZRun,
    SettlementStructureWire,
    ShellCellWire,
    TerritoryVolume,
    WorldMapCellWire,
)
from app.dataModel.worldPack.locationsIndexWire import LocationsIndexPin, LocationsIndexWire


def _world(uid: str = "w-render-read", **kwargs):
    defaults = {"world_uid": uid, "fine_cells_per_map_cell": 3000}
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

    def test_try_settlement_structure_none_without_file(self) -> None:
        facade = self._services().render
        self.assertIsNone(facade.try_settlement_structure(self.world, "loc-a"))
        self.assertFalse(facade.has_settlement_structure(self.world, "loc-a"))

    def test_try_settlement_structure_reads_blob(self) -> None:
        vol = TerritoryVolume(x0=10, y0=20, z0=0, x1=20, y1=30, z1=5)
        wire = SettlementStructureWire(
            settlement_uid="loc-a",
            districts=[
                DistrictStructureWire(
                    location_uid="d1",
                    areas=[
                        AreaStructureWire(
                            area_uid="a1",
                            slot=AreaSlotWire(
                                cells=[(10, 20)],
                                ground_z=0,
                                facing=Facing.NORTH,
                            ),
                            yard_cells=[
                                ShellCellWire(x=10, y=20, z=0, system_terrain="plains"),
                            ],
                        ),
                    ],
                ),
            ],
        )
        tmp = self.writer.encode_settlement_structure_tmp("loc-a", wire)
        self.writer.publish_settlement_structure(tmp, territory_volume=vol)
        facade = self._services().render
        self.assertTrue(facade.has_settlement_structure(self.world, "loc-a"))
        loaded = facade.try_settlement_structure(self.world, "loc-a")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.settlement_uid, "loc-a")
        self.assertEqual(len(loaded.districts), 1)
        self.assertIsNone(facade.try_settlement_structure(self.world, "missing"))

    def test_location_grid_merges_city_levels(self) -> None:
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
        self.writer.write_location_terrain("loc-a", chunk, territory_volume=vol)
        wire = SettlementStructureWire(
            settlement_uid="loc-a",
            districts=[
                DistrictStructureWire(
                    location_uid="d1",
                    areas=[
                        AreaStructureWire(
                            area_uid="a1",
                            slot=AreaSlotWire(
                                cells=[(10, 20)],
                                ground_z=0,
                                facing=Facing.NORTH,
                            ),
                            yard_cells=[],
                            buildings=[],
                            barrier_cells=[
                                ShellCellWire(
                                    x=10, y=20, z=0,
                                    system_building_element="wall",
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )
        tmp = self.writer.encode_settlement_structure_tmp("loc-a", wire)
        self.writer.publish_settlement_structure(tmp, territory_volume=vol)
        payload = PackMapGridRender(self._services().render).render_location_grid(
            self.world, "loc-a",
        )
        self.assertIn(LEVEL_SURFACE, payload.levels or {})
        self.assertIn(city_level_key(0), payload.levels or {})
        self.assertIn("#", (payload.levels or {})[city_level_key(0)])
        self.assertIn("structure:", payload.legend)


if __name__ == "__main__":
    unittest.main()
