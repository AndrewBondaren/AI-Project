import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app.application.engine.contracts.invocation.executionStore import Claim, ExecutionStore, OwnershipConflict
from app.application.engine.runtime.invocations.memoryExecutionStore import MemoryExecutionStore
from app.dataModel.engine.dag.identity import ExecutionId, WaitId
from app.dataModel.engine.dag.invocations.record import CompletedOutcome, FailedOutcome, StopOutcome
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore


class StopIntentTests(unittest.IsolatedAsyncioTestCase):
    outcomes = (CompletedOutcome(result_json='{"ok":true,"data":{"count":5},"error":null}'),
                FailedOutcome(diagnostic="response resolution failed"))

    async def exercise(self, first: ExecutionStore, second: ExecutionStore, key: ExecutionId, outcome: StopOutcome):
        await first.create(key, b"opaque legacy checkpoint")
        legacy = await first.load(key)
        self.assertIsNone(legacy.stop_intent)
        old = await first.claim(key, "first", 60)
        if isinstance(first, SQLiteExecutionStore):
            with first.db:
                first.db.execute("UPDATE dag_executions SET lease_until=0 WHERE execution_id=?", (key,))
            with self.assertRaises(OwnershipConflict):
                await first.record_stop_intent(old, 0, outcome)
            active = await second.claim(key, "next", 60)
        else:
            with patch("app.application.engine.runtime.invocations.memoryExecutionStore.monotonic", return_value=1e20):
                with self.assertRaises(OwnershipConflict):
                    await first.record_stop_intent(old, 0, outcome)
                active = await second.claim(key, "next", 60)
        for claim in (old, Claim(key, old.owner_id, active.fence), Claim(key, active.owner_id, old.fence)):
            with self.assertRaises(OwnershipConflict):
                await first.record_stop_intent(claim, 0, outcome)
        with self.assertRaises(OwnershipConflict):
            await second.record_stop_intent(active, 1, outcome)
        self.assertEqual(await second.load(key), legacy)
        intent = await second.record_stop_intent(active, 0, outcome)
        self.assertEqual((intent.execution_id, intent.stop_revision, intent.outcome), (key, 1, outcome))
        self.assertEqual(await first.record_stop_intent(active, 0, outcome), intent)
        for claim, revision, payload in ((old, 0, outcome), (active, 1, outcome),
                                         (active, 0, FailedOutcome(diagnostic="conflict"))):
            with self.assertRaises(OwnershipConflict):
                await first.record_stop_intent(claim, revision, payload)
        with self.assertRaises(OwnershipConflict):
            await second.checkpoint(active, 1, legacy.status, b"replacement")
        self.assertFalse(await first.cancel(key, 1, b"cancelled"))
        self.assertFalse(await first.cancel_child(key, 1, WaitId("wait")))
        saved = await first.load(key)
        self.assertEqual((saved.revision, saved.blob, saved.status, saved.stop_intent),
                         (1, legacy.blob, legacy.status, intent))
        return saved

    async def test_memory(self):
        store = MemoryExecutionStore()
        saved = [await self.exercise(store, store, ExecutionId(outcome.status), outcome) for outcome in self.outcomes]
        self.assertEqual(saved[0].stop_intent.store_id, saved[1].stop_intent.store_id)

    async def test_sqlite_reopen(self):
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dag.sqlite"
            with closing(sqlite3.connect(path)) as db:
                db.executescript(schema)
            saved = {}
            for outcome in self.outcomes:
                key = ExecutionId(outcome.status)
                with closing(sqlite3.connect(path)) as a, closing(sqlite3.connect(path)) as b:
                    saved[key] = await self.exercise(SQLiteExecutionStore(a), SQLiteExecutionStore(b), key, outcome)
            with closing(sqlite3.connect(path)) as db:
                store = SQLiteExecutionStore(db)
                for key, expected in saved.items():
                    self.assertEqual(await store.load(key), expected)
            self.assertEqual(len({cp.stop_intent.store_id for cp in saved.values()}), 1)

    async def test_identity_before_stop(self):
        schema = (Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql").read_text("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dag.sqlite"
            with closing(sqlite3.connect(path)) as a, closing(sqlite3.connect(path)) as b:
                a.executescript(schema)
                first, second = SQLiteExecutionStore(a), SQLiteExecutionStore(b)
                identity = await first.get_store_id()
                self.assertEqual(await second.get_store_id(), identity)
                self.assertFalse(a.in_transaction)
            with closing(sqlite3.connect(path)) as db, closing(sqlite3.connect(":memory:")) as other:
                store = SQLiteExecutionStore(db)
                self.assertEqual(await store.get_store_id(), identity)
                self.assertNotEqual(await SQLiteExecutionStore(other).get_store_id(), identity)
                key = ExecutionId("identity")
                await store.create(key, b"checkpoint")
                claim = await store.claim(key, "owner", 60)
                intent = await store.record_stop_intent(claim, 0, self.outcomes[0])
                self.assertEqual(intent.store_id, identity)
                self.assertEqual(await store.get_store_id(), identity)
        memory = MemoryExecutionStore()
        identity = await memory.get_store_id()
        await memory.create(ExecutionId("memory"), b"checkpoint")
        claim = await memory.claim(ExecutionId("memory"), "owner", 60)
        self.assertEqual((await memory.record_stop_intent(claim, 0, self.outcomes[0])).store_id, identity)
