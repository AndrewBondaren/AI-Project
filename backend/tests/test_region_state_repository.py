"""Wilderness 9a: real migrated SQLite, scoped CRUD and shared bulk batching."""

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from app.db.bulkSql import EXECUTEMANY_BATCH_SIZE, executemany_rows, iter_batches
from app.db.database import Database
from app.db.mapper import model_columns
from app.db.models.regionState import RegionStateRow
from app.db.repositories.sqlite.regionStateRepository import SqliteRegionStateRepository
from app.ids import region_uid, state_fingerprint


class RegionStateRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(str(Path(self.tmp.name) / "regions.sqlite"))
        await self.db.connect()
        await self.db.apply_migrations()
        async with self.db.transaction():
            await self.db.conn.execute(
                "INSERT INTO worlds(world_uid, name, created_at) VALUES ('world', 'W', 'now')")
            await self.db.conn.execute(
                "INSERT INTO worlds(world_uid, name, created_at) VALUES ('other', 'O', 'now')")
        self.repo = SqliteRegionStateRepository(self.db)

    async def asyncTearDown(self):
        await self.db.disconnect()
        self.tmp.cleanup()

    def state(self, name="forest", **changes):
        return replace(RegionStateRow(
            world_uid="world", region_uid=region_uid("world", name=name),
            current_type="forest", pending_target="steppe", progress=0.25,
            last_eval_tick=42, overrides={"density": 0.7, "label": "Тёмный лес"},
            history=[{"from_type": "plains", "to_type": "forest", "cause": "rain", "at": 40}],
            spec_fingerprint=state_fingerprint({"name": name}),
            created_at="2026-10-18T00:00:00Z", updated_at="2026-10-18T01:00:00Z",
        ), **changes)

    async def test_schema_matches_model_and_composite_identity(self):
        await self.db.validate_schema([RegionStateRow])
        async with self.db.conn.execute("PRAGMA table_info(region_states)") as cursor:
            columns = await cursor.fetchall()
        self.assertEqual({r["name"] for r in columns}, model_columns(RegionStateRow))
        self.assertEqual({r["name"]: r["pk"] for r in columns if r["pk"]},
                         {"world_uid": 1, "region_uid": 2})
        async with self.db.conn.execute("PRAGMA foreign_key_list(region_states)") as cursor:
            foreign_keys = await cursor.fetchall()
        self.assertTrue(any(r["table"] == "worlds" and r["from"] == "world_uid"
                            for r in foreign_keys))

    async def test_upsert_round_trip_and_replace_all_state_fields(self):
        state = self.state()
        self.assertIsNone(await self.repo.get(state.world_uid, state.region_uid))
        await self.repo.upsert(state)
        self.assertEqual(await self.repo.get(state.world_uid, state.region_uid), state)
        changed = replace(state, current_type="steppe", pending_target=None,
                          progress=0.0, last_eval_tick=100, overrides={},
                          history=[*state.history, {"from_type": "forest", "to_type": "steppe",
                                                   "cause": "dry", "at": 100}],
                          spec_fingerprint=None, updated_at="later")
        await self.repo.upsert(changed)
        self.assertEqual(await self.repo.get(state.world_uid, state.region_uid), changed)
        self.assertEqual(await self.repo.get_by_world("world"), [changed])

    async def test_all_keyed_operations_isolate_worlds(self):
        state = self.state()
        other = replace(state, world_uid="other", current_type="swamp")
        await self.repo.upsert_bulk([state, other])
        self.assertEqual(await self.repo.get("other", state.region_uid), other)
        self.assertEqual(await self.repo.mark_tombstone(
            "world", state.region_uid, updated_at="removed"), 1)
        tombstone = await self.repo.get("world", state.region_uid)
        self.assertEqual(tombstone, replace(state, tombstone=True, updated_at="removed"))
        self.assertIs(tombstone.tombstone, True)
        self.assertEqual(await self.repo.get_by_world("world"), [tombstone])
        self.assertEqual(await self.repo.cleanup_orphans("world"), 1)
        self.assertIsNone(await self.repo.get("world", state.region_uid))
        self.assertEqual(await self.repo.get_by_world("other"), [other])

    async def test_cleanup_keeps_live_rows_and_other_world_tombstones(self):
        live, dead = self.state("live"), self.state("dead", tombstone=True)
        other = replace(dead, world_uid="other")
        await self.repo.upsert_bulk([dead, other, live])
        self.assertEqual(await self.repo.cleanup_orphans("world"), 1)
        self.assertEqual(await self.repo.cleanup_orphans("world"), 0)
        self.assertEqual(await self.repo.get_by_world("world"), [live])
        self.assertEqual(await self.repo.get_by_world("other"), [other])

    async def test_missing_tombstone_and_empty_inputs_are_noops(self):
        self.assertEqual(await self.repo.mark_tombstone("world", "missing", updated_at="now"), 0)
        self.assertEqual(await self.repo.mark_tombstones(
            "world", ["missing"], updated_at="now"), 0)
        with patch.object(self.db, "transaction_if_needed", side_effect=AssertionError("empty write")):
            self.assertEqual(await self.repo.upsert_bulk([]), 0)
            self.assertEqual(await self.repo.mark_tombstones("world", [], updated_at="now"), 0)
        self.assertEqual(await self.repo.get_by_world("world"), [])

    async def test_bulk_crosses_shared_batch_boundary_and_updates(self):
        first = self.state()
        rows = [replace(first, region_uid=region_uid("world", name=str(i)))
                for i in range(EXECUTEMANY_BATCH_SIZE + 1)]
        module = "app.db.repositories.sqlite.regionStateRepository"
        with patch(f"{module}.executemany_rows", wraps=executemany_rows) as bulk, \
                patch("app.db.bulkSql.iter_batches", wraps=iter_batches) as batches:
            self.assertEqual(await self.repo.upsert_bulk(rows), len(rows))
            bulk.assert_called_once()
            batches.assert_called_once()
        self.assertEqual({s.region_uid for s in await self.repo.get_by_world("world")},
                         {s.region_uid for s in rows})
        changed = replace(rows[0], current_type="custom_terrain")
        self.assertEqual(await self.repo.upsert_bulk([changed]), 1)
        self.assertEqual(await self.repo.get("world", changed.region_uid), changed)
        with patch(f"{module}.executemany_rows", wraps=executemany_rows) as bulk, \
                patch("app.db.bulkSql.iter_batches", wraps=iter_batches) as batches:
            self.assertEqual(await self.repo.mark_tombstones(
                "world", [r.region_uid for r in rows], updated_at="gone"), len(rows))
            bulk.assert_called_once()
            batches.assert_called_once()
        self.assertTrue(all(r.tombstone for r in await self.repo.get_by_world("world")))
        self.assertEqual(await self.repo.cleanup_orphans("world"), len(rows))

    async def test_bulk_failure_rolls_back_previous_batches(self):
        state = self.state()
        rows = [replace(state, region_uid=str(i)) for i in range(EXECUTEMANY_BATCH_SIZE)]
        rows.append(replace(state, world_uid="missing-world"))
        with self.assertRaises(sqlite3.IntegrityError):
            await self.repo.upsert_bulk(rows)
        self.assertEqual(await self.repo.get_by_world("world"), [])
        await self.repo.upsert(state)
        self.assertEqual(await self.repo.get_by_world("world"), [state])

    async def test_writes_respect_caller_rollback(self):
        state = self.state()
        await self.repo.upsert(state)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            async with self.db.transaction():
                await self.repo.upsert(replace(state, progress=0.5))
                await self.repo.upsert_bulk([self.state("new")])
                await self.repo.mark_tombstone("world", state.region_uid, updated_at="gone")
                await self.repo.mark_tombstones("world", [state.region_uid], updated_at="gone")
                await self.repo.cleanup_orphans("world")
                raise RuntimeError("rollback")
        self.assertEqual(await self.repo.get_by_world("world"), [state])


if __name__ == "__main__":
    unittest.main()
