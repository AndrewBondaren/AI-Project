"""TR-PERF / TR-LAZY-LOAD — repo persist and scene load (no DAG)."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.mapCellService import MapCellService
from app.db.database import Database
from app.db.models.mapCell import MapCell
from app.db.models.world import World
from app.db.repositories.sqlite.mapCellRepository import SqliteMapCellRepository


def _minimal_world(uid: str = "w-perf-test") -> World:
    return World(
        world_uid=uid,
        name="Perf Test",
        created_at="2026-01-01T00:00:00Z",
        map_cell_size_m=1000,
        map_subsurface_depth=20,
        terrain_chunk_columns=32,
    )


def _map_cells_ddl() -> str:
    return """
    CREATE TABLE IF NOT EXISTS map_cells (
        world_uid TEXT NOT NULL,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        z INTEGER NOT NULL,
        system_terrain TEXT,
        system_building_element TEXT,
        system_material TEXT,
        is_structural INTEGER NOT NULL DEFAULT 0,
        travel_modifier_override REAL,
        system_danger_level_override TEXT,
        gap_width_override INTEGER,
        temperature_base INTEGER,
        rainfall INTEGER,
        location_uid TEXT,
        railing_sides TEXT,
        system_facing TEXT,
        display_facing TEXT,
        glass_material TEXT,
        hydrology TEXT,
        PRIMARY KEY (world_uid, x, y, z)
    );
    """


class MapCellPersistPerfTest(IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._db = Database(self._tmp.name)
        await self._db.connect()
        await self._db.conn.executescript(_map_cells_ddl())
        await self._db.conn.commit()
        self._repo = SqliteMapCellRepository(self._db)
        self._svc = MapCellService(self._repo)

    async def asyncTearDown(self) -> None:
        await self._db.disconnect()
        os.unlink(self._tmp.name)

    def _cells(self, n: int, *, terrain: str = "plains") -> list[MapCell]:
        return [
            MapCell(world_uid="w-perf-test", x=i, y=0, z=0, system_terrain=terrain)
            for i in range(n)
        ]

    async def test_executemany_upsert_terrain(self) -> None:
        cells = self._cells(50)
        n = await self._repo.upsert_terrain_skeleton(cells, conn=self._db.bootstrap_conn)
        self.assertEqual(n, 50)
        loaded = await self._repo.get_z_slice("w-perf-test", 0, 49, 0, 0, 0, 0)
        self.assertEqual(len(loaded), 50)

    async def test_insert_terrain_bulk_empty_world(self) -> None:
        cells = self._cells(20, terrain="forest")
        self.assertFalse(await self._repo.has_world_cells("w-perf-test"))
        n = await self._repo.insert_terrain_bulk(cells, conn=self._db.main_conn)
        self.assertEqual(n, 20)
        self.assertTrue(await self._repo.has_world_cells("w-perf-test"))
        loaded = await self._repo.get_z_slice("w-perf-test", 0, 19, 0, 0, 0, 0)
        self.assertEqual(len(loaded), 20)
        self.assertTrue(all(c.system_terrain == "forest" for c in loaded))

    async def test_save_pass_insert_only(self) -> None:
        cells = self._cells(5, terrain="tundra")
        result = await self._svc.save_pass(cells, "terrain", insert_only=True)
        self.assertEqual(result.succeeded, 5)


    async def test_has_column_cells(self) -> None:
        self.assertFalse(await self._svc.has_column_cells("w-perf-test", 5, 5))
        await self._repo.insert_bulk_ignore([
            MapCell(world_uid="w-perf-test", x=5, y=5, z=1, system_terrain="plains"),
        ])
        self.assertTrue(await self._svc.has_column_cells("w-perf-test", 5, 5))

    async def test_get_scene_volume_bbox(self) -> None:
        world = _minimal_world()
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for dz in range(3):
                    await self._repo.insert_bulk_ignore([MapCell(
                        world_uid=world.world_uid,
                        x=100 + dx, y=200 + dy, z=dz,
                        system_terrain="plains",
                    )])
        volume = await self._svc.get_scene_volume(
            world, 100, 200, 1, xy_radius=1, z_above=1,
        )
        xs = {c.x for c in volume}
        ys = {c.y for c in volume}
        self.assertEqual(xs, {99, 100, 101})
        self.assertEqual(ys, {199, 200, 201})
        self.assertEqual(len(volume), 27)


if __name__ == "__main__":
    unittest.main()
