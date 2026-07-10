"""TR-PAR-5/6 — bootstrap DB connection isolation."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest import IsolatedAsyncioTestCase

from app.application.worldData.bootstrapMapCellWriter import BootstrapMapCellWriter
from app.db.database import BULK_CACHE_SIZE, Database
from app.db.models.mapCell import MapCell
from app.db.repositories.sqlite.mapCellRepository import SqliteMapCellRepository


async def _pragma_int(conn, name: str) -> int:
    async with conn.execute(f"PRAGMA {name}") as cur:
        row = await cur.fetchone()
    return int(row[0])


def _map_cell_patches_ddl() -> str:
    return """
    CREATE TABLE IF NOT EXISTS map_cell_patches (
        world_uid TEXT NOT NULL,
        x INTEGER NOT NULL,
        y INTEGER NOT NULL,
        z INTEGER NOT NULL,
        layer_kind TEXT NOT NULL DEFAULT 'structure',
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


class DatabaseBootstrapConnTest(IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._db = Database(self._tmp.name)
        await self._db.connect()
        await self._db.main_conn.executescript(_map_cell_patches_ddl())
        await self._db.main_conn.commit()
        self._repo = SqliteMapCellRepository(self._db)
        self._writer = BootstrapMapCellWriter(self._db, self._repo)

    async def asyncTearDown(self) -> None:
        await self._db.disconnect()
        os.unlink(self._tmp.name)

    async def test_bootstrap_conn_has_bulk_pragma(self) -> None:
        bs = self._db.bootstrap_conn
        self.assertEqual(await _pragma_int(bs, "synchronous"), 1)  # NORMAL
        self.assertEqual(await _pragma_int(bs, "temp_store"), 2)  # MEMORY
        self.assertEqual(await _pragma_int(bs, "cache_size"), BULK_CACHE_SIZE)

    async def test_main_conn_unchanged_during_bulk_lock(self) -> None:
        main = self._db.main_conn
        before_sync = await _pragma_int(main, "synchronous")
        before_cache = await _pragma_int(main, "cache_size")
        async with self._db.bulk_write_lock():
            self.assertIs(self._db.conn, self._db.main_conn)
            self.assertEqual(await _pragma_int(main, "synchronous"), before_sync)
            self.assertEqual(await _pragma_int(main, "cache_size"), before_cache)

    async def test_bulk_write_lock_serializes(self) -> None:
        started: list[str] = []
        finished: list[str] = []

        async def job(name: str, delay: float) -> None:
            async with self._db.bulk_write_lock():
                started.append(name)
                await asyncio.sleep(delay)
                finished.append(name)

        await asyncio.gather(
            job("a", 0.05),
            job("b", 0.01),
        )
        self.assertEqual(started, ["a", "b"])
        self.assertEqual(finished, ["a", "b"])

    async def test_writer_writes_visible_on_main_conn(self) -> None:
        cells = [
            MapCell(world_uid="w-par5", x=1, y=2, z=0, system_terrain="plains"),
        ]
        async with self._writer.session():
            await self._writer.write_terrain(cells, insert_only=True)
        async with self._db.main_conn.execute(
            "SELECT system_terrain FROM map_cell_patches WHERE world_uid = ? AND x = ?",
            ["w-par5", 1],
        ) as cur:
            row = await cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "plains")


if __name__ == "__main__":
    unittest.main()
