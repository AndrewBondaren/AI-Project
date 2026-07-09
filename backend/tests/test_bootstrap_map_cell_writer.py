"""TR-PAR-6 — BootstrapMapCellWriter unit tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.bootstrapMapCellWriter import BootstrapMapCellWriter
from app.db.database import Database
from app.db.models.mapCell import MapCell
from app.db.repositories.sqlite.mapCellRepository import SqliteMapCellRepository


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


class BootstrapMapCellWriterTest(IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._db = Database(self._tmp.name)
        await self._db.connect()
        await self._db.main_conn.executescript(_map_cells_ddl())
        await self._db.main_conn.commit()
        self._repo = SqliteMapCellRepository(self._db)
        self._writer = BootstrapMapCellWriter(self._db, self._repo)

    async def asyncTearDown(self) -> None:
        await self._db.disconnect()
        os.unlink(self._tmp.name)

    def _cells(self, n: int, *, terrain: str = "plains") -> list[MapCell]:
        return [
            MapCell(world_uid="w-writer", x=i, y=0, z=0, system_terrain=terrain)
            for i in range(n)
        ]

    async def test_write_terrain_insert_only_on_bootstrap_conn(self) -> None:
        cells = self._cells(3, terrain="forest")
        async with self._writer.session():
            n = await self._writer.write_terrain(cells, insert_only=True)
        self.assertEqual(n, 3)
        loaded = await self._repo.get_z_slice("w-writer", 0, 2, 0, 0, 0, 0)
        self.assertEqual(len(loaded), 3)

    async def test_write_terrain_chunk_batch_single_transaction(self) -> None:
        chunks = [
            self._cells(2, terrain="hills"),
            [
                MapCell(world_uid="w-writer", x=10 + i, y=0, z=0, system_terrain="hills")
                for i in range(2)
            ],
        ]
        async with self._writer.session():
            n = await self._writer.write_terrain_chunk_batch(chunks, insert_only=True)
        self.assertEqual(n, 4)
        self.assertTrue(await self._repo.has_world_cells("w-writer"))

    async def test_write_climate_visible_on_main(self) -> None:
        base = self._cells(1)
        async with self._writer.session():
            await self._writer.write_terrain(base, insert_only=True)
        climate_cells = [
            MapCell(
                world_uid="w-writer", x=0, y=0, z=0,
                system_terrain="plains",
                temperature_base=15,
                rainfall=50,
            ),
        ]
        async with self._writer.session():
            n = await self._writer.write_climate(climate_cells)
        self.assertEqual(n, 1)
        async with self._db.main_conn.execute(
            "SELECT temperature_base, rainfall FROM map_cells WHERE world_uid = ? AND x = 0",
            ["w-writer"],
        ) as cur:
            row = await cur.fetchone()
        self.assertEqual(row[0], 15)
        self.assertEqual(row[1], 50)

    async def test_session_disabled_yields_without_lock(self) -> None:
        async with self._writer.session(enabled=False):
            pass


if __name__ == "__main__":
    unittest.main()
