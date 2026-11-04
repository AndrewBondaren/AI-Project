import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
from threading import Barrier
import unittest

from pydantic import ValidationError

from app.application.worldData.bakeOperations.service import BakeService
from app.application.worldData.bakeOperations.worker import BakeWorker
from app.dataModel.world.bakeOperation.admission import BakeConflict, Joined, Started
from app.dataModel.world.bakeOperation.record import BakeError, BakeErrorKind, BakeResult, BakeStatus, Waiter, PublicationOperationId
from app.dataModel.world.bakeOperation.request import BakeKind, BakeRequest
from app.db.repositories.sqlite.bakeOperations.operationStore import BakeFenceLost, SQLiteBakeOperations


class BakeRequestTests(unittest.TestCase):
    def test_publication_id_rejects_foreign_enum_with_valid_text(self):
        identifier = PublicationOperationId("RUNNING")
        self.assertEqual(identifier.value, "RUNNING")
        self.assertNotIsInstance(identifier, str)
        self.assertNotEqual(identifier, "RUNNING")
        with self.assertRaises(TypeError):
            PublicationOperationId(BakeStatus.RUNNING)

    def test_format_version_on_wire(self):
        fields = dict(world_uid="w", kind="FULL", scope=[], source_revision="r1",
                      preparation_contract_version="1", parameters_fingerprint="a"*64)
        default = BakeRequest.model_validate_json(json.dumps(fields))
        self.assertEqual(default.version, 1)
        self.assertEqual(default, BakeRequest.model_validate_json(json.dumps(dict(fields, version=1))))
        for value in (True, 1.0, "1", None, 0, 2):
            with self.subTest(version=value), self.assertRaises(ValidationError):
                BakeRequest.model_validate_json(json.dumps(dict(fields, version=value)))


class LoseReply(sqlite3.Connection):
    lose_reply = False

    def __exit__(self, *args):
        result = super().__exit__(*args)
        if self.lose_reply:
            self.lose_reply = False
            raise sqlite3.OperationalError("lost commit reply")
        return result


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

    async def stage(self, token, request) -> PublicationOperationId:
        self.stages += 1
        self.started.set()
        await self.finish.wait()
        return PublicationOperationId(token.operation_id)

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
        self.second.publishing(current, PublicationOperationId("publish-1"))

        def publish(db, record):
            db.execute("INSERT INTO test_publications VALUES(?,?)", (record.publication_operation_id.value, "tile-pack"))
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
            record = restarted.poll(current.operation_id, self.waiter)
            self.assertIs(type(record.publication_operation_id), PublicationOperationId)
            self.assertEqual(record.result, BakeResult(result_ref="tile-pack"))
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
        self.assertEqual(self.second.read(token.operation_id).error,
                         BakeError(kind=BakeErrorKind.PUBLICATION_ROLLED_BACK, message="rollback confirmed"))
        next_op = self.first.admit(self.request, self.other)
        self.assertIsInstance(next_op, Started)
        self.assertTrue(self.service.cancel_operation(next_op.operation_ref))
        with self.assertRaises(BakeFenceLost):
            self.first.begin(next_op.owner_token)

    def test_submit_rejects_missing_models_before_readiness(self):
        from unittest.mock import patch
        for cached in (None, BakeResult(result_ref="cached")):
            with patch.object(self.binding, "ready", return_value=cached) as ready:
                for request, waiter in ((None, self.waiter), (self.request, None)):
                    with self.assertRaises(TypeError):
                        self.service.submit(request, waiter)
                ready.assert_not_called()
        self.assertEqual(self.a.execute("SELECT count(*) FROM bake_operations").fetchone()[0], 0)

    async def test_preparation_error_and_legacy_text_round_trip(self):
        from unittest.mock import patch
        from app.db.mapper import from_row, to_row
        from app.db.models.bakeOperation import BakeOperation

        token = self.first.admit(self.request, self.waiter).owner_token
        with patch.object(self.binding, "stage", side_effect=RuntimeError("stage failed")):
            await self.service.worker.run(token)
        expected = BakeError(kind=BakeErrorKind.PREPARATION_FAILED, message="stage failed")
        self.b.row_factory = sqlite3.Row
        row = from_row(BakeOperation, self.b.execute("SELECT * FROM bake_operations").fetchone())
        self.assertEqual(row.error, expected)
        columns, values = to_row(row)
        self.assertEqual(BakeError.decode(values[columns.index("error")]), expected)
        self.assertEqual(self.second.read(token.operation_id).error, expected)
        with self.a:
            self.a.execute("UPDATE bake_operations SET error=?", ("old message",))
        self.assertEqual(self.second.read(token.operation_id).error, BakeError(kind=BakeErrorKind.LEGACY, message="old message"))
        with self.assertRaises(TypeError):
            BakeError.encode("untyped")

    async def test_foreign_rollback_evidence_keeps_claim_after_takeover(self):
        from types import SimpleNamespace
        old = self.first.admit(self.request, self.waiter).owner_token
        self.first.begin(old)
        self.first.publishing(old, PublicationOperationId("pub-1"))
        self.expire()
        self.binding.evidence = SimpleNamespace(reason="unverified")
        with self.assertRaisesRegex(TypeError, "RolledBack"):
            await BakeWorker(self.second, self.binding).run(self.second.recover())
        saved = self.first.read(old.operation_id)
        self.assertIs(saved.status, BakeStatus.RECOVERY_REQUIRED)
        self.assertIsNone(saved.error)
        self.assertIsInstance(self.first.admit(self.request, self.other), Joined)

    def test_terminal_subclasses_round_trip_as_declared_contracts(self):
        from app.db.mapper import from_row
        from app.db.models.bakeOperation import BakeOperation

        class DetailedResult(BakeResult):
            detail: str

        class DetailedError(BakeError):
            detail: str

        self.b.row_factory = sqlite3.Row
        for status in (BakeStatus.SUCCEEDED, BakeStatus.FAILED):
            with self.subTest(status=status):
                owner = self.first.admit(self.request, self.waiter).owner_token
                self.first.begin(owner)
                if status == BakeStatus.SUCCEEDED:
                    self.first.publishing(owner, PublicationOperationId("pub"))
                    self.first.publication(owner, lambda *_: DetailedResult(result_ref="pack", detail="private"))
                    expected = (BakeResult(result_ref="pack"), None)
                else:
                    error = DetailedError(kind=BakeErrorKind.PREPARATION_FAILED, message="failed", detail="private")
                    self.first.prepared_terminal(owner, None, error)
                    expected = (None, BakeError(kind=error.kind, message=error.message))
                row = self.b.execute("SELECT * FROM bake_operations WHERE operation_id=?", (owner.operation_id,)).fetchone()
                for record in (self.second.read(owner.operation_id), from_row(BakeOperation, row)):
                    self.assertIs(record.status, status)
                    self.assertEqual((record.result, record.error), expected)

    def test_generic_mapper_restores_bake_domain_types(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from app.db.mapper import from_row, to_row
        from app.db.models.bakeOperation import BakeOperation, BakeWaiter
        from app.dataModel.world.bakeOperation.record import DeliveryStatus
        token = self.first.admit(self.request, self.waiter).owner_token
        self.first.begin(token)
        self.first.publishing(token, PublicationOperationId("pub-1"))
        self.b.row_factory = sqlite3.Row
        row = from_row(BakeOperation, self.b.execute("SELECT * FROM bake_operations").fetchone())
        self.assertIs(row.kind, BakeKind.FULL)
        self.assertIs(row.status, BakeStatus.PUBLISHING)
        self.assertIs(type(row.publication_operation_id), PublicationOperationId)
        columns, values = to_row(row)
        self.assertEqual(values[columns.index("publication_operation_id")], "pub-1")
        self.assertIsNone(row.result)
        self.assertIsNone(values[columns.index("result_blob")])
        result = BakeResult(result_ref="tile-pack")
        self.first.publication(token, lambda db, record: result)
        published = from_row(BakeOperation, self.b.execute("SELECT * FROM bake_operations").fetchone())
        self.assertIs(type(published.result), BakeResult)
        self.assertEqual(published.result, result)
        columns, values = to_row(published)
        self.assertEqual(values[columns.index("result_blob")], result.model_dump_json())
        with self.assertRaisesRegex(TypeError, "BakeResult"):
            to_row(replace(published, result=BakeError(kind=BakeErrorKind.LEGACY, message="oops")))
        with self.assertRaisesRegex(TypeError, "PublicationOperationId"):
            to_row(replace(published, publication_operation_id=SimpleNamespace(value="foreign")))
        waiter = from_row(BakeWaiter, self.b.execute("SELECT * FROM bake_waiters").fetchone())
        self.assertIs(waiter.delivery_status, DeliveryStatus.SUBSCRIBED)

    async def test_lost_reply_after_publication_commit_returns_success(self):
        from unittest.mock import patch

        db = sqlite3.connect(self.path, factory=LoseReply)
        self.addCleanup(db.close)
        db.execute("CREATE TABLE effects(id TEXT PRIMARY KEY)")
        store = SQLiteBakeOperations(db)
        owner = store.admit(self.request, self.waiter).owner_token
        self.binding.finish.set()
        def publish(conn, record):
            conn.execute("INSERT INTO effects VALUES(?)", (record.publication_operation_id.value,))
            db.lose_reply = True
            return BakeResult(result_ref="confirmed")

        with patch.object(self.binding, "publish", side_effect=publish) as callback:
            await BakeWorker(store, self.binding).run(owner)
            callback.assert_called_once()
        self.assertEqual(self.second.read(owner.operation_id).result, BakeResult(result_ref="confirmed"))
        self.assertEqual(self.b.execute("SELECT count(*) FROM effects").fetchone()[0], 1)
        self.assertEqual(self.b.execute("SELECT count(*) FROM bake_world_claims").fetchone()[0], 0)

    async def test_lost_reconcile_reply_confirms_committed_outcome(self):
        from app.dataModel.world.bakeOperation.record import RolledBack
        from unittest.mock import patch

        db = sqlite3.connect(self.path, factory=LoseReply)
        self.addCleanup(db.close)
        store = SQLiteBakeOperations(db)
        result = BakeResult(result_ref="confirmed")
        for evidence, status, expected_result, error in (
            (result, BakeStatus.SUCCEEDED, result, None),
            (RolledBack("proven"), BakeStatus.FAILED, None, BakeError(kind=BakeErrorKind.PUBLICATION_ROLLED_BACK, message="proven")),
        ):
            with self.subTest(status=status):
                old = self.first.admit(self.request, self.waiter).owner_token
                self.first.begin(old)
                self.first.publishing(old, PublicationOperationId("pub-1"))
                self.expire()
                owner = store.recover()

                def reconcile(conn, record):
                    db.lose_reply = True
                    return evidence

                with patch.object(self.binding, "reconcile", side_effect=reconcile) as callback:
                    await BakeWorker(store, self.binding).run(owner)
                    callback.assert_called_once()
                record = self.second.read(old.operation_id)
                self.assertEqual((record.status, record.result, record.error), (status, expected_result, error))
                self.assertEqual(self.b.execute("SELECT count(*) FROM bake_world_claims").fetchone()[0], 0)
                self.assertEqual(self.binding.publishes, 0)
                with self.assertRaises(BakeFenceLost):
                    store.uncertain(old, PublicationOperationId("pub-1"))
                with self.assertRaises(BakeFenceLost):
                    store.uncertain(owner, PublicationOperationId("different"))

    async def test_recovery_rejects_missing_publication_id_before_reconcile(self):
        from unittest.mock import patch

        owner = self.first.admit(self.request, self.waiter).owner_token
        self.assertIsNone(self.first.read(owner.operation_id).publication_operation_id)
        self.first.begin(owner)
        self.assertIsNone(self.first.read(owner.operation_id).publication_operation_id)
        self.first.publishing(owner, PublicationOperationId("publication"))
        for status in (BakeStatus.PUBLISHING, BakeStatus.RECOVERY_REQUIRED):
            for invalid_id in (None, ""):
                with self.subTest(status=status, invalid_id=invalid_id):
                    with self.a:
                        self.a.execute("UPDATE bake_operations SET status=?,publication_operation_id=?,lease_until=0 "
                                       "WHERE operation_id=?", (status, invalid_id, owner.operation_id))
                    replacement = self.second.recover()
                    with patch.object(self.binding, "reconcile", return_value=BakeResult(result_ref="unverified")) as reconcile:
                        with self.assertRaises(ValueError):
                            await BakeWorker(self.second, self.binding).run(replacement)
                        reconcile.assert_not_called()
                    row = self.a.execute("SELECT status,result_blob FROM bake_operations JOIN bake_world_claims "
                                         "USING(world_uid,operation_id) WHERE operation_id=?", (owner.operation_id,)).fetchone()
                    self.assertEqual(row, (status, None))

    async def test_unknown_publication_holds_claim_and_recovery_fences_stale_worker(self):
        old = self.first.admit(self.request, self.waiter).owner_token
        self.first.begin(old)
        self.first.publishing(old, PublicationOperationId("publication"))
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
