"""Append-only schema and rollback probes, not a production transaction adapter."""

import sqlite3
import unittest
import asyncio
import threading
from unittest.mock import patch
from app.application.publication.errors import UnknownCommitOutcome
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationPhase, OperationKind
from app.dataModel.artifacts.lifecycle.operation.claim import PublicationTerminal
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.db.mapper import from_row, to_row
from tests.snapshotCore.support.fixtures import (
    CORE_MODELS, new_database, started, tick, stage, operation, insert, snapshot_values,
    run_async, live_database, live_started, live_tick,
)


class AtomicSnapshotCommitTests(unittest.TestCase):
    def setUp(self):
        self.conn = new_database()
        self.addCleanup(self.conn.close)

    def test_every_core_table_forbids_update_delete_and_replace_with_recursive_triggers_off(self):
        started(self.conn)
        tick(self.conn, players=("p1",))
        stage(self.conn)
        self.assertEqual(self.conn.execute("PRAGMA recursive_triggers").fetchone()[0], 0)
        for model in CORE_MODELS:
            table, key = model.__table__, model.__pk__
            row = self.conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
            self.assertIsNotNone(row, table)
            values = dict(row)
            for statement, args in (
                (f"UPDATE {table} SET {key}={key} WHERE {key}=?", (row[key],)),
                (f"DELETE FROM {table} WHERE {key}=?", (row[key],)),
                (f"INSERT OR REPLACE INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values())),
            ):
                with self.subTest(table=table, statement=statement), self.assertRaises(sqlite3.IntegrityError):
                    self.conn.execute(statement, args)
            self.assertEqual(dict(self.conn.execute(f"SELECT * FROM {table} WHERE {key}=?", (row[key],)).fetchone()), values)

    def test_mapper_roundtrip_and_frozen_rows_cover_every_table(self):
        started(self.conn)
        tick(self.conn, players=("p1",))
        stage(self.conn)
        for model in CORE_MODELS:
            row = self.conn.execute(f"SELECT * FROM {model.__table__} LIMIT 1").fetchone()
            mapped = from_row(model, row)
            names, values = to_row(mapped)
            self.assertEqual(dict(zip(names, values)), dict(row))

    def test_schema_failure_rolls_back_prepared_snapshot_rows_without_advancing_heads(self):
        started(self.conn)
        self.conn.execute("SAVEPOINT snapshot_attempt")
        operation(self.conn, "failed")
        insert(self.conn, "world_snapshots", **snapshot_values(self.conn, "failed"))
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "player_publications", publication_id="bad", player_uid="p1", predecessor_id=None,
                   publication_seq=1, player_snapshot_id="missing", operation_id="failed")
        self.conn.execute("ROLLBACK TO snapshot_attempt")
        self.conn.execute("RELEASE snapshot_attempt")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM world_snapshots").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM publication_operations WHERE operation_id='failed'").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT snapshot_head_id FROM world_publications ORDER BY publication_seq DESC LIMIT 1").fetchone()[0], None)

    def test_adapter_world_player_history_and_outcome_commit_or_rollback_as_one(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                claims = []
                with self.assertRaises(RuntimeError):
                    await live_tick(bundle, "failed", fail=True, claims=claims)
                self.assertEqual(await bundle[2].read("w1"), expected)
                self.assertIsNone(await bundle[3].read("p1"))
                async with bundle[0].conn.execute("SELECT count(*) FROM world_snapshots") as cursor:
                    self.assertEqual((await cursor.fetchone())[0], 0)
                refusal = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.CONFLICT, operation_id="failed",
                    request_fingerprint="b" * 64, committed=None, diagnostics=(FieldPathError(path=(), message="conflict"),))
                await bundle[-1].record_refusal(claims[0], refusal)
                self.assertEqual((await bundle[-1].read("failed")).terminal, refusal)
                claim, success = await live_tick(bundle)
                self.assertEqual((await bundle[-1].read("tick")).terminal, success)
                self.assertEqual((await bundle[2].read("w1")).snapshot_head, success.committed.world_snapshot)
                self.assertEqual(await bundle[3].read("p1"), success.committed.player_snapshots[0])
        run_async(check())

    def test_adapter_lost_commit_ack_quarantines_connection_and_recovers_terminal(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                db, commits, world, players, history, operations = bundle
                original = commits.driver.commit
                reached_commit, release_commit = asyncio.Event(), asyncio.Event()
                async def lose_ack(conn):
                    async with conn.execute("SELECT count(*) FROM world_snapshots WHERE operation_id='tick'") as cursor:
                        publication = bool((await cursor.fetchone())[0])
                    if publication:
                        reached_commit.set()
                        await release_commit.wait()
                    cancelled = await original(conn)
                    if publication:
                        raise OSError("lost COMMIT acknowledgement")
                    return cancelled
                claims = []
                with patch.object(commits.driver, "commit", lose_ack):
                    pending = asyncio.create_task(live_tick(bundle, claims=claims))
                    await reached_commit.wait()
                    queued = asyncio.create_task(operations.read("tick"))
                    await asyncio.sleep(0.02)
                    self.assertFalse(queued.done())
                    release_commit.set()
                    with self.assertRaises(UnknownCommitOutcome):
                        await pending
                    with self.assertRaises(UnknownCommitOutcome):
                        await queued
                with self.assertRaises(UnknownCommitOutcome):
                    await operations.read("tick")
                with self.assertRaises(UnknownCommitOutcome):
                    await operations.record_refusal(claims[0], SnapshotApplyResult(category=SnapshotApplyOutcomeKind.REJECTED,
                        operation_id="tick", request_fingerprint="b" * 64, committed=None,
                        diagnostics=(FieldPathError(path=(), message="must not replace unknown outcome"),)))
                async with live_database(db.path, seed=False) as recovery:
                    result = (await recovery[-1].read("tick")).terminal
                    self.assertIs(result.category, SnapshotApplyOutcomeKind.COMMITTED)
                    with patch.object(recovery[2], "read", side_effect=AssertionError("retry must not read current targets")):
                        retry = await recovery[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, "tick", "w1", "a" * 64, "b" * 64)
                    self.assertIsInstance(retry, PublicationTerminal)
                    self.assertEqual(retry.record.terminal, result)
        run_async(check())

    def test_lost_rollback_ack_and_failed_close_keep_registry_quarantined(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                db, commits, world, players, history, operations = bundle
                rollback = commits.driver.rollback
                async def lose_ack(conn):
                    async with conn.execute("SELECT count(*) FROM world_snapshots WHERE operation_id='tick'") as cursor:
                        publication = bool((await cursor.fetchone())[0])
                    cancelled = await rollback(conn)
                    if publication:
                        raise OSError("lost ROLLBACK acknowledgement")
                    return cancelled
                async def failed_close(conn):
                    raise OSError("driver close failed")
                with patch.object(commits.driver, "rollback", lose_ack), patch.object(commits.driver, "close", failed_close):
                    with self.assertRaises(UnknownCommitOutcome):
                        await live_tick(bundle, fail=True)
                with self.assertRaises(UnknownCommitOutcome):
                    await operations.read("tick")
                with self.assertRaises(UnknownCommitOutcome):
                    async with commits.transaction("retry"):
                        self.fail("quarantined connection must not issue a scope")
                async with live_database(db.path, seed=False) as recovery:
                    self.assertEqual(await recovery[2].read("w1"), expected)
                    self.assertIsNone((await recovery[-1].read("tick")).terminal)
        run_async(check())

    def test_adapter_body_cancellation_rolls_back_without_fabricating_a_terminal(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                entered, hold = asyncio.Event(), asyncio.Event()
                pending = asyncio.create_task(live_tick(bundle, entered=entered, hold=hold))
                await entered.wait()
                pending.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await pending
                self.assertEqual(await bundle[2].read("w1"), expected)
                self.assertIsNone(await bundle[3].read("p1"))
                record = await bundle[-1].read("tick")
                self.assertIs(record.phase, OperationPhase.APPLYING)
                self.assertIsNone(record.terminal)
        run_async(check())

    def test_adapter_commit_cancellation_drains_worker_before_releasing_gate(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                entered = asyncio.Event()
                worker_started, release = threading.Event(), threading.Event()
                def trace(sql):
                    if sql == "COMMIT" and entered.is_set():
                        worker_started.set()
                        if not release.wait(5):
                            raise AssertionError("test failed to release COMMIT worker")
                await bundle[0].conn.set_trace_callback(trace)
                pending = asyncio.create_task(live_tick(bundle, entered=entered))
                try:
                    self.assertTrue(await asyncio.to_thread(worker_started.wait, 4))
                    pending.cancel()
                    observer = asyncio.create_task(bundle[2].read("w1"))
                    await asyncio.sleep(0.02)
                    self.assertFalse(pending.done())
                    self.assertFalse(observer.done())
                    release.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await pending
                    self.assertIsNotNone((await observer).snapshot_head)
                    result = (await bundle[-1].read("tick")).terminal
                    self.assertIs(result.category, SnapshotApplyOutcomeKind.COMMITTED)
                finally:
                    release.set()
                    await bundle[0].conn.set_trace_callback(None)
                    if not pending.done():
                        await pending
        run_async(check())

    def test_adapter_cancellation_while_rolling_back_does_not_become_the_original_error(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                publication_written, worker_started, release = threading.Event(), threading.Event(), threading.Event()
                def trace(sql):
                    if sql.startswith("INSERT INTO world_publications") and "tick-pub" in sql:
                        publication_written.set()
                    if sql == "ROLLBACK" and publication_written.is_set():
                        worker_started.set()
                        release.wait(5)
                await bundle[0].conn.set_trace_callback(trace)
                pending = asyncio.create_task(live_tick(bundle, fail=True))
                try:
                    self.assertTrue(await asyncio.to_thread(worker_started.wait, 4))
                    pending.cancel()
                    await asyncio.sleep(0.02)
                    self.assertFalse(pending.done())
                    release.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await pending
                    await bundle[0].conn.set_trace_callback(None)
                    self.assertEqual(await bundle[2].read("w1"), expected)
                    self.assertIsNone((await bundle[-1].read("tick")).terminal)
                finally:
                    release.set()
                    await bundle[0].conn.set_trace_callback(None)
                    if not pending.done():
                        await pending
        run_async(check())
