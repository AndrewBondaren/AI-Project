import asyncio
import sqlite3
import threading
from contextlib import AsyncExitStack, asynccontextmanager, closing, contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch
from uuid import uuid4

from app.application.artifacts.staging.artifactStaging import TypedArtifactStager
from app.application.worldData.generators.hydrology.encoding.packFormats import ROOT_FORMAT, SHARD_FORMAT
from app.application.worldData.pack.read.pinnedManifestReader import PinnedManifestReader
from app.application.worldData.pack.spatial.openWaterBlobReader import OpenWaterBlobReader
from app.db.repositories.sqlite.worldPack.pinnedManifestGuard import PinnedManifestGuard
from app.db.repositories.sqlite.worldPack.pinnedSpatialReader import PinnedSpatialReader
from app.application.worldData.pack.encoding.packManifestCodec import encode_candidate_manifest
from app.dataModel.artifacts.lifecycle.holders import ArtifactRetentionHolder, PinHolder
from app.dataModel.engine.dag.invocations.record import FailedOutcome
from app.dataModel.worldPack.meta.spatial.domainRoot import SpatialDatasetKind, SpatialDomainRootRef
from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from app.db.repositories.sqlite.worldPack.executionPins import ExecutionPins, PinIntent, PackClosed, PackIdentityConflict, PackIntentUnavailable
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.snapshotCore.support.fixtures import live_database, operation, STAMP
from tests.spatial_pack.test_manifest_pin_retention import register_read_formats


class ExecutionPinFixture(IsolatedAsyncioTestCase):
    async def connect_pack(self, seed):
        self.stack = await self.enterAsyncContext(AsyncExitStack())
        bundle = await self.stack.enter_async_context(live_database(str(self.path), seed=seed))
        self.bundle = bundle
        self.fixture = SqliteBlobFixture(bundle)
        register_read_formats(self.fixture, self.path)
        self.pins = await self.adapter(bundle, self.fixture)
        f = self.fixture
        self.manifest_reader = PinnedManifestReader(
            PinnedManifestGuard(self.pins, f.backend.contract, 1, 100000), f.backend)
        self.spatial_reader = PinnedSpatialReader(self.pins, f.backend, 100000,
            OpenWaterBlobReader(f.service._registry, f.catalog, f.holders))

    async def adapter(self, bundle, fixture):
        return await ExecutionPins.bind(self.dag, bundle[2], fixture.holders, fixture.service._registry,
                                        fixture.backend.contract, 1, 100000)

    async def asyncSetUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory())) / "pack.db"
        db = self.enterContext(closing(sqlite3.connect(self.path.with_name("dag.db"))))
        schema = Path(__file__).resolve().parents[2] / "app/db/migrations/0001_initial.sql"
        db.executescript(schema.read_text("utf8"))
        self.dag = SQLiteExecutionStore(db)
        await self.dag.create("execution", b"checkpoint")
        self.claim = await self.dag.claim("execution", "worker", 60)
        self.intent = PinIntent(await self.dag.get_store_id(), "execution", "inv", "water", "pin-a", "w1")
        await self.connect_pack(True)
        commits, publications = self.bundle[1:3]
        async with commits.transaction("init") as scope:
            self.head = await publications.initialize(scope, "w1")
        self.manifest = await self.publish("a", 1)
        self.assertEqual(await self.pins.acquire(self.intent), self.manifest)

    async def publish(self, name, cells):
        f = self.fixture
        lease = await f.open(name)
        folder = Path(__file__).with_name("fixtures")
        async def stage(contract, file):
            data = (folder / file).read_bytes()
            return await TypedArtifactStager(contract, 1, f.service._registry, f.service).stage(lease, data)
        self.root = await stage(ROOT_FORMAT, "retention-root.tlv")
        self.shard = await stage(SHARD_FORMAT, "retention-shard.tlv")
        manifest = WorldPackManifest(world_uid="w1", pack_version="2.0.0", world_map_cells=cells,
            spatial_roots=(SpatialDomainRootRef(domain=SpatialDatasetKind.HYDROLOGY_OPEN_WATER, root=self.root),))
        ref = await f.stager.stage(lease, encode_candidate_manifest(manifest))
        await f.service.finish_preparation(lease, (self.root, self.shard, ref))
        await f.ledger.claim_publication(lease.kind, name, "w1", "a"*64, "b"*64)
        async with self.bundle[1].transaction(name) as scope, f.catalog._scopes.bind(scope):
            head = self.head.model_copy(update={"publication_id": name, "pack_hash": ref.content_hash})
            await self.bundle[2].compare_append(scope, self.head, head)
            for child in (self.root, self.shard):
                await f.holders.acquire(child, ArtifactRetentionHolder(artifact=ref))
            self.head = head
        return ref

    async def stop(self):
        return await self.dag.record_stop_intent(self.claim, 0, FailedOutcome(diagnostic="stop"))

    async def reopen(self):
        await self.stack.aclose()
        await self.connect_pack(False)

class ExecutionPinTests(ExecutionPinFixture):
    async def test_lost_reply(self):
        cmd = await self.stop()
        receipt = await self.pins.close(cmd)
        await self.reopen()
        self.assertEqual(await self.pins.close(cmd), receipt)
        persisted = await self.pins.read_closed(cmd)
        assert persisted is not None
        self.assertEqual(persisted, receipt)
        final = await self.dag.finalize(self.claim, cmd.stop_revision, persisted)
        self.assertEqual(final.final_revision, cmd.stop_revision + 1)
        self.assertEqual(final.stop_intent, cmd)
        async with self.bundle[0].conn.execute("SELECT COUNT(*) FROM pack_execution_closed") as cursor:
            self.assertEqual((await cursor.fetchone())[0], 1)
        await self.assert_holds()

    async def assert_holds(self):
        self.assertTrue(await self.fixture.holders.is_held(self.manifest, PinHolder(pin_id=self.intent.pin_id)))
        for child in (self.root, self.shard):
            self.assertTrue(await self.fixture.holders.is_held(child, ArtifactRetentionHolder(artifact=self.manifest)))

    async def test_close_without_pins_and_independent_namespace(self):
        foreign_db = self.enterContext(closing(sqlite3.connect(self.path.with_name("other-dag.db"))))
        schema = Path(__file__).resolve().parents[2] / "app/db/migrations/0001_initial.sql"
        foreign_db.executescript(schema.read_text("utf8"))
        foreign = SQLiteExecutionStore(foreign_db)
        await foreign.create(self.intent.execution_id, b"another execution")
        claim = await foreign.claim(self.intent.execution_id, "worker", 60)
        command = await foreign.record_stop_intent(claim, 0, FailedOutcome(diagnostic="foreign"))
        with self.assertRaises(PackIdentityConflict):
            await ExecutionPins.bind(foreign, self.bundle[2], self.fixture.holders,
                self.fixture.service._registry, self.fixture.backend.contract, 1, 100000)
        other = await ExecutionPins.bind(foreign, self.bundle[2], self.fixture.holders,
            self.fixture.service._registry, self.fixture.backend.contract, 1, 100000, binding_key="other-dag")
        with self.assertRaises(PackIdentityConflict):
            await self.pins.close(command)
        with patch.object(foreign, "load", side_effect=OSError("offline")):
            with self.assertRaises(PackIntentUnavailable):
                await other.close(command)
        await other.close(command)
        with self.assertRaises(PackClosed):
            await other.acquire(replace(self.intent, store_id=command.store_id, pin_id="new"))
        self.assertEqual(await self.pins.acquire(self.intent), self.manifest)
        await self.assert_holds()

    async def test_conflicts(self):
        second_pin = replace(self.intent, pin_id="second-pin", logical_read_key="other-read")
        await self.pins.acquire(second_pin)
        for bad_pin in (replace(self.intent, world_uid="w2"), replace(self.intent, pin_id="foreign"),
                        replace(self.intent, execution_id="foreign")):
            with self.assertRaises(PackIdentityConflict):
                await self.pins.acquire(bad_pin)
        cmd = await self.stop()
        for after in (False, True):
            for change in (dict(store_id=uuid4()), dict(stop_revision=99), dict(execution_id="absent")):
                with self.assertRaises(PackIdentityConflict):
                    await self.pins.close(cmd.model_copy(update=change))
            if not after:
                self.assertEqual(await self.pins.acquire(self.intent), self.manifest)
            self.assertEqual((await self.pins.close(cmd)).stop_revision, cmd.stop_revision)
            await self.assert_holds()

    async def test_stale_worker(self):
        gate = asyncio.Event()
        ready = asyncio.Event()
        catalog = self.fixture.catalog
        guard = catalog.guard

        @asynccontextmanager
        async def before_guard(ref):
            if ref == self.shard:
                ready.set()
                await gate.wait()
            async with guard(ref):
                yield

        with patch.object(catalog, "guard", before_guard):
            worker = asyncio.create_task(self.spatial_reader.read_shard(self.intent, self.shard))
            await asyncio.wait_for(ready.wait(), 10)
            await self.pins.close(await self.stop())
            with patch.object(Path, "open", autospec=True) as opened:
                gate.set()
                with self.assertRaises(PackClosed):
                    await worker
                opened.assert_not_called()

    async def test_stream_first(self):
        await self.stream_first(cancel=False)

    async def test_cancelled_stream_first(self):
        await self.stream_first(cancel=True)

    async def stream_first(self, cancel):
        observer = await self.stack.enter_async_context(live_database(str(self.path), seed=False))
        other = await self.adapter(observer, SqliteBlobFixture(observer))
        started, attempted, release, closed = (threading.Event() for _ in range(4))
        closed_at_insert = []
        def trace(sql):
            if sql == "BEGIN IMMEDIATE":
                attempted.set()
            if "INSERT INTO pack_execution_closed" in sql:
                closed_at_insert.append(closed.is_set())
        await observer[0].conn.set_trace_callback(trace)
        actual_open = Path.open
        @contextmanager
        def instrument(path, *args, **kwargs):
            with actual_open(path, *args, **kwargs) as stream:
                if path.name != self.root.content_hash:
                    yield stream
                    return
                started.set()
                if not release.wait(10):
                    raise TimeoutError()
                yield stream
            closed.set()
        cmd = await self.stop()
        with patch.object(Path, "open", instrument):
            read = asyncio.create_task(self.spatial_reader.read_root(self.intent, self.root))
            self.assertTrue(await asyncio.to_thread(started.wait, 5))
            close = asyncio.create_task(other.close(cmd))
            try:
                self.assertTrue(await asyncio.to_thread(attempted.wait, 5))
                if cancel:
                    read.cancel()
                    await asyncio.sleep(0)
                    self.assertFalse(read.done())
                self.assertFalse(close.done())
            finally:
                release.set()
            await close
            self.assertTrue(closed.is_set())
            self.assertTrue(closed_at_insert and all(closed_at_insert))
            if cancel:
                with self.assertRaises(asyncio.CancelledError):
                    await read
            else:
                await read
        with self.assertRaises(PackClosed):
            await self.spatial_reader.read_shard(self.intent, self.shard)
        await self.assert_holds()

    async def test_crash_and_shared_shard(self):
        second = await self.publish("b", 2)
        self.assertEqual(await self.pins.acquire(self.intent), self.manifest)
        intent_b = replace(self.intent, invocation_id="other", pin_id="pin-b")
        self.assertEqual(await self.pins.acquire(intent_b), second)
        shard_bytes = Path(__file__).with_name("fixtures").joinpath("retention-shard.tlv").read_bytes()
        self.assertEqual(await self.spatial_reader.read_shard(self.intent, self.shard), shard_bytes)
        self.assertEqual(await self.spatial_reader.read_shard(intent_b, self.shard), shard_bytes)
        cmd = await self.stop()
        receipt = await self.pins.close(cmd)
        with (patch.object(self.dag, "get_store_id", side_effect=OSError("offline")),
              patch.object(self.dag, "load", side_effect=OSError("offline")) as load):
            await self.reopen()
            with self.assertRaises(PackIntentUnavailable):
                await ExecutionPins.bind(self.dag, self.bundle[2], self.fixture.holders,
                    self.fixture.service._registry, self.fixture.backend.contract, 1, 100000,
                    binding_key="never-registered")
            with self.assertRaises(PackIdentityConflict):
                await self.pins.close(cmd.model_copy(update={"store_id": uuid4()}))
            with self.assertRaises(PackIdentityConflict):
                await self.pins.close(cmd.model_copy(update={"stop_revision": cmd.stop_revision + 1}))
            with self.assertRaises(PackIntentUnavailable):
                await self.pins.close(cmd.model_copy(update={"execution_id": "no-receipt"}))
            self.assertEqual(await self.pins.close(cmd), receipt)
            for intent in (self.intent, intent_b):
                with self.assertRaises(PackClosed):
                    await self.pins.acquire(intent)
                with self.assertRaises(PackClosed):
                    await self.spatial_reader.read_shard(intent, self.shard)
            load.assert_not_awaited()
        await self.assert_holds()
        self.assertTrue(await self.fixture.holders.is_held(second, PinHolder(pin_id="pin-b")))
        self.assertTrue(await self.fixture.holders.is_held(self.shard, ArtifactRetentionHolder(artifact=second)))

    async def test_direct_constructor_cannot_grant_foreign_namespace(self):
        foreign = replace(self.intent, store_id=uuid4(), pin_id="foreign-pin")
        with self.assertRaises(TypeError):
            ExecutionPins(foreign.store_id, self.dag, self.bundle[2], self.fixture.holders,
                          self.fixture.service._registry, self.fixture.backend.contract, 1, 100000)
        unbound = ExecutionPins(self.bundle[2], self.fixture.holders, self.fixture.service._registry,
                                self.fixture.backend.contract, 1, 100000)
        with self.assertRaises(PackIdentityConflict):
            await unbound.acquire(foreign)
        with self.assertRaises(PackIdentityConflict):
            await self.pins.acquire(foreign)
        async with self.bundle[0].conn.execute(
                "SELECT COUNT(*) FROM pack_execution_pins WHERE store_id=?", (str(foreign.store_id),)) as cursor:
            self.assertEqual((await cursor.fetchone())[0], 0)
        self.assertFalse(await self.fixture.holders.is_held(self.manifest, PinHolder(pin_id=foreign.pin_id)))
        await self.pins.close(await self.stop())
        with patch.object(Path, "open", autospec=True) as opened:
            with self.assertRaises(PackIdentityConflict):
                await self.spatial_reader.read_root(foreign, self.root)
            with self.assertRaises(PackClosed):
                await self.spatial_reader.read_root(self.intent, self.root)
            opened.assert_not_called()

    async def test_cold_replay_after_dag_connection_closed(self):
        command = await self.stop()
        receipt = await self.pins.close(command)
        with patch.object(self.dag, "get_store_id", side_effect=sqlite3.ProgrammingError("incorrect bindings")):
            with self.assertRaisesRegex(sqlite3.ProgrammingError, "incorrect bindings"):
                await self.adapter(self.bundle, self.fixture)
        self.dag.db.close()
        with patch.object(self.dag, "load", wraps=self.dag.load) as load:
            await self.reopen()
            self.assertEqual(await self.pins.close(command), receipt)
            with self.assertRaises(PackClosed):
                await self.spatial_reader.read_root(self.intent, self.root)
            load.assert_not_awaited()
        await self.assert_holds()


class JournalSchemaTests(TestCase):
    def test_operation_holder_chain_in_initial_schema(self):
        migrations = Path(__file__).resolve().parents[2] / "app/db/migrations"
        with closing(sqlite3.connect(":memory:")) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.executescript((migrations / "0001_initial.sql").read_text("utf8"))
            db.execute("INSERT INTO artifact_catalog VALUES ('a','blob','test.blob',1,?,1,NULL)", ("a"*64,))
            db.execute("INSERT INTO worlds(world_uid,name,created_at) VALUES ('w1','w1',?)", (STAMP,))
            operation(db, "op", phase="preparing", bound=False)
            for event, predecessor, seq, kind in (("e1", None, 1, "acquire"), ("e2", "e1", 2, "release")):
                db.execute("INSERT INTO artifact_holder_events VALUES (?,'a','operation','op',1,NULL,NULL,NULL,?,?,?,NULL)",
                           (event, predecessor, seq, kind))
            rows = db.execute("SELECT predecessor_id,event_kind,pin_id FROM artifact_holder_events ORDER BY event_seq")
            self.assertEqual(rows.fetchall(), [(None, "acquire", None), ("e1", "release", None)])
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
