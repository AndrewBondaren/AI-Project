"""9c: live entity state below patches, immutable L0/L2 pack snapshots."""

import io
import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from pydantic import TypeAdapter

from app.application.worldData.mapCells.patchStoreService import PatchStoreService
from app.application.worldData.pack import WorldPackPaths, WorldPackWriter
from app.application.worldData.pack.read.packReadServices import build_pack_read_services
from app.application.worldData.pack.read.regionStateOverlay import RegionStateOverlay, overlay_terrain
from app.application.worldData.regions.regionStateMapping import state_to_row
from app.core.loggingConfig import setup_logging, _remove_facade_handlers, flush_console_queue
from app.dataModel.regions.regionState import RegionState
from app.dataModel.terrain.worldTerrainRegistry import TerrainKey
from app.dataModel.worldPack import WorldMapCellWire
from app.dataModel.worldPack.bake.layerPriority import MapLayerKind
from app.dataModel.worldPack.meta.wildernessRegionEntry import WildernessRegionEntry
from app.dataModel.worldPack.wire.fineTerrainChunkWire import (
    FineTerrainChunkWire, FineTerrainColumnWire, FineTerrainZRun,
)
from app.dataModel.worldPack.wire.mergeMapCells import CellContribution, LayerSlice
from app.db.models.world import World
from app.db.models.mapCell import MapCell
from app.db.database import Database
from app.db.repositories.sqlite.regionStateRepository import SqliteRegionStateRepository

key = TypeAdapter(TerrainKey).validate_python


def entry(uid, x0=0, x1=10):
    return WildernessRegionEntry(region_uid=uid, entry_type="forest", current_type="forest",
                                 bbox=dict(x_min=x0, x_max=x1, y_min=0, y_max=10),
                                 status="declared")


def row(uid="r", terrain="steppe", tombstone=False):
    return state_to_row(RegionState(region_uid=uid, current_type=terrain, tombstone=tombstone),
                        world_uid="w", created_at="now", updated_at="now")


class OverlayKeyTests(unittest.TestCase):
    def test_key_contract(self):
        baked = key("forest")
        state = RegionState(region_uid="r", current_type="steppe")
        self.assertEqual(overlay_terrain(baked, "r", {"r": state}, key("plains")), "steppe")
        self.assertIs(overlay_terrain(baked, None, {"r": state}, key("plains")), baked)
        self.assertIs(overlay_terrain(baked, "missing", {"r": state}, key("plains")), baked)
        same = state.model_copy(update={"current_type": baked})
        self.assertIs(overlay_terrain(baked, "r", {"r": same}, key("plains")), baked)
        dead = state.model_copy(update={"tombstone": True})
        self.assertEqual(overlay_terrain(baked, "r", {"r": dead}, key("custom_background")),
                         "custom_background")


class OverlayMergeTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_lower_layer_and_patch_priority_without_mutation(self):
        repo = Mock(get_many=AsyncMock(return_value=[row()]))
        overlay = RegionStateOverlay(repo)
        world = World("w", "World", "now")
        cells = {}
        for kind in MapLayerKind:
            cell = CellContribution(x=int(kind), y=0, z=12, region_uid="r",
                                    system_terrain="forest", system_material="soil",
                                    hydrology={"role": "land"}, is_structural=True)
            cells[(int(kind), 0, 12)] = [LayerSlice(kind=kind, cell=cell)]
        before = {coord: [layer.model_dump() for layer in layers] for coord, layers in cells.items()}
        views = await overlay.merge(world, cells, [])
        repo.get_many.assert_awaited_once_with("w", ["r"])
        for view in views:
            self.assertEqual(view.system_terrain, "forest" if view.x == 0 else "steppe")
            self.assertEqual(view.system_material, "soil")
            self.assertEqual(view.hydrology, {"role": "land"})
            self.assertEqual(view.z, 12)
            self.assertTrue(view.is_structural)
        self.assertEqual(before, {coord: [layer.model_dump() for layer in layers]
                                  for coord, layers in cells.items()})

    async def test_patch_wins_and_baked_winner_uid_is_preserved(self):
        repo = Mock(get_many=AsyncMock(return_value=[row(), row("neighbor", "mountain")]))
        base = CellContribution(x=0, y=0, z=1, region_uid="r", system_terrain="forest")
        patch = base.model_copy(update={"system_terrain": "crater"})
        cells = {(0, 0, 1): [LayerSlice(kind=MapLayerKind.WORLD_MAP, cell=base),
                            LayerSlice(kind=MapLayerKind.PATCH, cell=patch)]}
        with self.assertLogs("app.application.worldData.regions.regionStateLog", "WARNING") as logs:
            views = await RegionStateOverlay(repo).merge(
                World("w", "W", "now"), cells, [entry("r"), entry("neighbor", 10, 20)])
        self.assertEqual(views[0].system_terrain, "crater")
        self.assertEqual(base.region_uid, "r")
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(logs.records[0].neighbors, ["neighbor"])
        self.assertEqual(logs.records[0].activity, "overlap_rerank_deferred")

    async def test_logging_facade_json_sink(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = io.StringIO()
            root_level = logging.getLogger().level
            try:
                setup_logging(level=logging.WARNING, profile="server", logs_dir=Path(tmp), stream=stream)
                repo = Mock(get_many=AsyncMock(return_value=[row()]))
                cells = {(x, 0, 0): [LayerSlice(kind=MapLayerKind.WORLD_MAP, cell=CellContribution(
                    x=x, y=0, z=0, region_uid="r", system_terrain="forest"))] for x in range(10)}
                await RegionStateOverlay(repo).merge(World("w", "W", "now"), cells,
                                                     [entry("r"), entry("other"), entry("far", 50, 60)])
                flush_console_queue()
                for handler in logging.getLogger().handlers:
                    handler.flush()
                lines = (Path(tmp) / "region_state/regionStateLog.log").read_text().splitlines()
                self.assertEqual(len(lines), 1)
                record = json.loads(lines[0])
                self.assertEqual(record["level"], "WARNING")
                self.assertEqual(record["world_uid"], "w")
                self.assertEqual(record["region_uid"], "r")
                self.assertEqual(record["neighbors"], ["other"])
                self.assertIn("region_state | overlap_rerank_deferred |", record["msg"])
                self.assertNotIn("overlap_rerank_deferred", stream.getvalue())
            finally:
                _remove_facade_handlers()
                logging.getLogger().setLevel(root_level)


class PackOverlayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.world = World("w", "World", "now", fine_cells_per_map_cell=1000)
        self.db_path = str(Path(self.tmp.name) / "game.db")
        self.paths = WorldPackPaths.from_db_parent(self.db_path, "w")
        self.writer = WorldPackWriter(self.paths)
        self.writer.write_world_map_tile(0, 0, [WorldMapCellWire(
            tx=0, ty=0, surface_z=10, system_terrain="forest", region_uid="r")], cells_per_side=32)
        self.writer.save_manifest()
        self.repo = Mock(get_many=AsyncMock(return_value=[row()]))
        self.services = build_pack_read_services("w", PatchStoreService(), db_path=self.db_path,
                                                  region_state_repo=self.repo)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_l0_live_reads_raw_snapshot_and_no_stale_state(self):
        view = await self.services.gameplay.get_cell(self.world, 0, 0, 10)
        self.assertEqual(view.system_terrain, "steppe")
        self.repo.get_many.return_value = [row(terrain="swamp")]
        view = await self.services.gameplay.get_cell(self.world, 0, 0, 10)
        self.assertEqual(view.system_terrain, "swamp")
        _, raw = self.services.context.reader_for(self.world).read_world_map_tile(0, 0)
        self.assertEqual(raw[0].system_terrain, "forest")
        self.repo.get_many.return_value = []
        self.assertEqual((await self.services.gameplay.get_cell(self.world, 0, 0, 10)).system_terrain,
                         "forest")

    async def test_scene_batches_state_query(self):
        views = await self.services.gameplay.get_scene_volume(
            self.world, 1, 1, 10, xy_radius=1, z_below=0, z_above=0)
        self.assertEqual(len(views), 9)
        self.assertTrue(all(view.system_terrain == "steppe" for view in views))
        self.repo.get_many.assert_awaited_once_with("w", ["r"])

    async def test_sql_store_transition_without_rebake_and_terrain_delta_patch(self):
        db = Database(self.db_path)
        await db.connect()
        try:
            await db.apply_migrations()
            async with db.transaction():
                await db.conn.execute(
                    "INSERT INTO worlds(world_uid, name, created_at) VALUES ('w', 'World', 'now')")
            repo = SqliteRegionStateRepository(db)
            await repo.upsert(row())
            services = build_pack_read_services("w", PatchStoreService(), db_path=self.db_path,
                                                region_state_repo=repo)
            self.assertEqual((await services.gameplay.get_cell(self.world, 0, 0, 10)).system_terrain,
                             "steppe")
            patch_repo = Mock(get_z_slice=AsyncMock(return_value=[MapCell(
                world_uid="w", x=0, y=0, z=10, system_terrain="crater", layer_kind="terrain_delta")]))
            patched = build_pack_read_services("w", PatchStoreService(patch_repo), db_path=self.db_path,
                                               region_state_repo=repo)
            self.assertEqual((await patched.gameplay.get_cell(self.world, 0, 0, 10)).system_terrain,
                             "crater")
            self.assertEqual(await repo.get("w", "r"), row())
            _, raw = services.context.reader_for(self.world).read_world_map_tile(0, 0)
            self.assertEqual(raw[0].system_terrain, "forest")
        finally:
            await db.disconnect()

    async def test_l2_and_tombstone_keep_z_and_material(self):
        chunk = FineTerrainChunkWire(cx=0, cy=0, chunk_columns=32, columns=[
            FineTerrainColumnWire(lx=0, ly=0, region_uid="r", runs=[
                FineTerrainZRun(z0=10, z1=10, system_terrain="forest", system_material="soil")])])
        self.writer.write_wilderness_chunk(0, 0, chunk)
        self.writer.save_manifest()
        self.services.context.invalidate_pack(self.world)
        view = await self.services.gameplay.get_cell(self.world, 0, 0, 10)
        self.assertEqual(view.system_terrain, "steppe")
        self.assertEqual(view.system_material, "soil")
        self.repo.get_many.return_value = [row(tombstone=True)]
        self.world.terrain_masks = {"default_plains": {"system_terrain": "custom_background"}}
        view = await self.services.gameplay.get_cell(self.world, 0, 0, 10)
        self.assertEqual(view.system_terrain, "custom_background")
        self.assertEqual(view.system_material, "soil")
        self.assertEqual(view.z, 10)
        raw = self.services.context.reader_for(self.world).read_wilderness_chunk(0, 0, 0, 0)
        self.assertEqual(raw, chunk)

    async def test_merged_debug_and_footprint_use_overlay(self):
        exported = await self.services.debug.get_debug_export_cells(self.world)
        self.assertEqual(exported[0].system_terrain, "steppe")
        footprint = await self.services.gameplay.get_footprint_terrain(
            self.world, x0=0, y0=0, x1=30, y1=30)
        self.assertEqual(footprint[0].system_terrain, "steppe")
        sliced = await self.services.debug.get_merged_z_slice(self.world, 0, 1, 0, 1, 10, 10)
        self.assertTrue(all(cell.system_terrain == "steppe" for cell in sliced))
