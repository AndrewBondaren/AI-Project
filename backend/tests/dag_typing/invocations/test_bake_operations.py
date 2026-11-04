import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
from threading import Barrier
import unittest

from app.application.worldData.bakeOperations.service import BakeService
from app.application.worldData.bakeOperations.worker import BakeWorker
from app.dataModel.world.bakeOperation.admission import BakeConflict, Joined, Started
from app.dataModel.world.bakeOperation.record import BakeResult, BakeStatus, Waiter
from app.dataModel.world.bakeOperation.request import BakeKind, BakeRequest
from app.db.repositories.sqlite.bakeOperations.operationStore import BakeFenceLost, SQLiteBakeOperations


class Binding:
    def __init__(self):
        self.started = asyncio.Event()
        self.finish = asyncio.Event()
        self.stages = 0
        self.publishes = 0
        self.current = None
        self.evidence = None

    def authorize(self, request, waiter, operation):
        pass

    def ready(self, request):
        return self.current

    async def stage(self, token, request):
        self.stages += 1
        self.started.set()
        await self.finish.wait()
        return token.operation_id

    def publish(self, db, record):
        self.publishes += 1
        return BakeResult(result_ref="baked")

    def reconcile(self, db, record):
        return self.evidence


class BakeOperationsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "worlds.db"
        self.a, self.b = (sqlite3.connect(self.path) for _ in range(2))
        for connection in (self.a, self.b):
            self.addCleanup(connection.close)
            connection.execute("PRAGMA foreign_keys=ON")
        schema = Path(__file__).resolve().parents[3] / "app/db/migrations/0001_initial.sql"
        self.a.executescript(schema.read_text("utf-8"))
        with self.a:
            self.a.executemany("INSERT INTO worlds(world_uid,name,created_at) VALUES(?,?,datetime('now'))",
                               (("world", "world"), ("other", "other")))
        self.first, self.second = SQLiteBakeOperations(self.a), SQLiteBakeOperations(self.b)
        self.binding = Binding()
        self.service = BakeService(BakeWorker(self.first, self.binding))
        self.request = BakeRequest(world_uid="world", kind=BakeKind.FULL, scope=("a", "b"), source_revision="r1",
                                   preparation_contract_version="1", parameters_fingerprint="a"*64)
        self.waiter = Waiter(execution_id="run", invocation_id="call-1/world", step_index=0)
        self.other = self.waiter.model_copy(update={"step_index": 1})

    def expire(self):
        with self.b:
            self.b.execute("UPDATE bake_operations SET lease_until=0")

    def test_simultaneous_admissions_and_scope_conflicts(self):
        barrier = Barrier(2)
        def submit(waiter):
            db = sqlite3.connect(self.path)
            try:
                barrier.wait(timeout=5)
                return SQLiteBakeOperations(db).admit(self.request, waiter)
            finally:
                db.close()
        with ThreadPoolExecutor(2) as pool:
            admissions = list(pool.map(submit, (self.waiter, self.other)))
        self.assertEqual({type(value) for value in admissions}, {Started, Joined})
        self.assertEqual(admissions[0].operation_ref, admissions[1].operation_ref)
        for update in ({"kind": BakeKind.LIGHT}, {"kind": BakeKind.DETAILED}, {"source_revision": "r2"}):
            self.assertIsInstance(self.second.admit(self.request.model_copy(update=update), self.waiter), BakeConflict)
        detailed = self.request.model_copy(update={"world_uid": "other", "kind": BakeKind.DETAILED})
        self.assertIsInstance(self.second.admit(detailed, self.waiter), Started)
        self.assertIsInstance(self.first.admit(detailed.model_copy(update={"scope": ("b", "a")}), self.other), BakeConflict)

    async def test_compute_survives_detach_and_replays_delivery_until_ack(self):
        started = self.service.submit(self.request, self.waiter)
        await asyncio.wait_for(self.binding.started.wait(), 3)
        client = BakeService(BakeWorker(self.second, self.binding))
        self.assertIsInstance(client.submit(self.request, self.other), Joined)
        for waiter in (self.waiter, self.other):
            client.detach(started.operation_ref, waiter)
        late = self.waiter.model_copy(update={"step_index": 2})
        self.assertIsInstance(client.submit(self.request, late), Joined)
        self.binding.finish.set()
        async with asyncio.timeout(3):
            while client.poll(started.operation_ref, late) is None:
                await asyncio.sleep(.01)
        result = client.poll(started.operation_ref, late)
        self.assertEqual(result.result, BakeResult(result_ref="baked"))
        self.assertEqual(result, client.poll(started.operation_ref, late))
        client.acknowledge(started.operation_ref, late)
        self.assertIsNone(client.poll(started.operation_ref, late))
        self.assertIsNone(client.poll(started.operation_ref, self.waiter))
        self.assertEqual((self.binding.stages, self.binding.publishes), (1, 1))

    async def test_second_readiness_check(self):
        started = self.service.submit(self.request, self.waiter)
        self.binding.current = BakeResult(result_ref="already-published")
        async with asyncio.timeout(3):
            while self.service.poll(started.operation_ref, self.waiter) is None:
                await asyncio.sleep(.01)
        self.assertEqual(self.first.read(started.operation_ref).result, self.binding.current)
        self.assertEqual(self.service.submit(self.request, self.other), self.binding.current)
        self.assertEqual((self.binding.stages, self.binding.publishes), (0, 0))

    async def test_different_worlds_stage_concurrently_without_waiters(self):
        one = self.service.submit(self.request, self.waiter)
        client = BakeService(BakeWorker(self.second, self.binding))
        two = client.submit(self.request.model_copy(update={"world_uid": "other"}), self.other)
        async with asyncio.timeout(3):
            while self.binding.stages < 2:
                await asyncio.sleep(.01)
        self.service.detach(one.operation_ref, self.waiter)
        client.detach(two.operation_ref, self.other)
        self.binding.finish.set()
        async with asyncio.timeout(3):
            while any(self.first.read(op).status != BakeStatus.SUCCEEDED for op in (one.operation_ref, two.operation_ref)):
                await asyncio.sleep(.01)
        self.assertEqual(self.binding.publishes, 2)

    async def test_lifecycle_recovers_abandoned_pending_operation(self):
        started = self.first.admit(self.request, self.waiter)
        self.expire()
        self.binding.finish.set()
        replacement = BakeService(BakeWorker(self.second, self.binding))
        lifecycle = asyncio.create_task(replacement.serve())
        try:
            async with asyncio.timeout(3):
                while self.first.read(started.operation_ref).status != BakeStatus.SUCCEEDED:
                    await asyncio.sleep(.01)
        finally:
            lifecycle.cancel()
            await asyncio.gather(lifecycle, return_exceptions=True)
        with self.assertRaises(BakeFenceLost):
            self.first.heartbeat(started.owner_token)

    async def test_restart_after_publication_commit_before_delivery(self):
        self.a.execute("CREATE TABLE test_publications(id TEXT PRIMARY KEY, result_ref TEXT NOT NULL)")
        old = self.first.admit(self.request, self.waiter).owner_token
        self.first.begin(old)
        with self.assertRaises(ValueError):
            self.first.begin(old)
        self.expire()
        current = self.second.recover()
        self.second.begin(current)
        self.second.publishing(current, "publish-1")

        def publish(db, record):
            db.execute("INSERT INTO test_publications VALUES(?,?)", (record.publication_operation_id, "tile-pack"))
            return BakeResult(result_ref="tile-pack")

        with self.assertRaises(BakeFenceLost):
            self.first.publication(old, publish)
        self.second.publication(current, publish)
        self.a.close()
        self.b.close()
        db = sqlite3.connect(self.path)
        self.addCleanup(db.close)
        restarted = BakeService(BakeWorker(SQLiteBakeOperations(db), self.binding))
        for _ in range(2):
            self.assertEqual(restarted.poll(current.operation_id, self.waiter).result, BakeResult(result_ref="tile-pack"))
        restarted.acknowledge(current.operation_id, self.waiter)
        self.assertIsNone(restarted.poll(current.operation_id, self.waiter))
        self.assertEqual(db.execute("SELECT * FROM test_publications").fetchall(), [("publish-1", "tile-pack")])

    async def test_publication_exception_retains_claim_until_proven_rollback(self):
        from app.dataModel.world.bakeOperation.record import RolledBack
        from unittest.mock import patch
        token = self.first.admit(self.request, self.waiter).owner_token
        self.binding.finish.set()
        with patch.object(self.binding, "publish", side_effect=RuntimeError("commit result unavailable")):
            with self.assertRaises(RuntimeError):
                await self.service.worker.run(token)
        self.assertEqual(self.second.read(token.operation_id).status, BakeStatus.RECOVERY_REQUIRED)
        self.assertFalse(self.service.cancel_operation(token.operation_id))
        self.expire()
        self.binding.evidence = RolledBack("rollback confirmed")
        await self.service.worker.run(self.first.recover())
        self.assertEqual(self.second.read(token.operation_id).error, "rollback confirmed")
        next_op = self.first.admit(self.request, self.other)
        self.assertIsInstance(next_op, Started)
        self.assertTrue(self.service.cancel_operation(next_op.operation_ref))
        with self.assertRaises(BakeFenceLost):
            self.first.begin(next_op.owner_token)

    async def test_unknown_publication_holds_claim_and_recovery_fences_stale_worker(self):
        old = self.first.admit(self.request, self.waiter).owner_token
        self.first.begin(old)
        self.first.publishing(old, "publication")
        self.expire()
        replacement = self.second.recover()
        self.assertEqual(replacement.operation_id, old.operation_id)
        self.assertGreater(replacement.fence, old.fence)
        with self.assertRaises(BakeFenceLost):
            self.first.publication(old, self.binding.publish)
        self.assertEqual(self.binding.publishes, 0)
        await BakeWorker(self.second, self.binding).run(replacement)
        self.assertEqual(self.first.read(old.operation_id).status, BakeStatus.RECOVERY_REQUIRED)
        self.assertIsInstance(self.first.admit(self.request.model_copy(update={"kind": BakeKind.LIGHT}), self.other), BakeConflict)
        self.expire()
        self.binding.evidence = BakeResult(result_ref="confirmed")
        await BakeWorker(self.first, self.binding).run(self.first.recover())
        self.assertEqual(self.first.read(old.operation_id).result, self.binding.evidence)
        self.assertIsInstance(self.second.admit(self.request, self.other), Started)
