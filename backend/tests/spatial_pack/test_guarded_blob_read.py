"""P2R-B through the public reader, real SQLite guard/holders and file backend."""
import asyncio
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from app.application.artifacts.lifecycle.artifactGc import ArtifactGarbageCollector
from app.application.engine.runtime.invocations.invocationCoordinator import InvocationCoordinator
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.worldData.generators.hydrology.encoding.packFormats import ROOT_FORMAT, SHARD_FORMAT
from app.application.worldData.pack.spatial.openWaterBlobReader import OpenWaterBlobReader, SpatialBlobReadError
from app.dataModel.artifacts.lifecycle.holders import OperationHolder
from app.dataModel.engine.dag.identity import ExecutionId, PlanRevision
from app.dataModel.engine.dag.invocations.record import InvocationStatus
from app.db.repositories.sqlite.dagExecutions.executionStore import SQLiteExecutionStore
from app.dataModel.hydrology.pack.profile import ROOT_V1
from app.dataModel.spatial.readFailureReason import SpatialReadFailureReason as Reason
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from app.storage.artifacts.blobRead import read_verified_file
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
from tests.dag_typing.invocations.test_world_calls import runtime
from tests.snapshotCore.support.fixtures import live_database
from tests.spatial_pack.test_verified_blob_read import descriptor


class GuardedReadTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bundle = await self.enterAsyncContext(live_database())
        self.state = SqliteBlobFixture(self.bundle)
        self.lease = await self.state.open("reader-op")
        self.holder = OperationHolder(lease=self.lease)
        self.registry = ArtifactFormatRegistryBinding()
        for contract in (ROOT_FORMAT, SHARD_FORMAT):
            self.registry.register(contract, ContentAddressedBlobBackend(
                Path(self.bundle[0].path).parent / "artifacts", contract, self.state.leases))
        self.reader = OpenWaterBlobReader(self.registry, self.state.catalog, self.state.holders)

    async def reserve(self, contract):
        return await self.state.catalog.reserve(self.lease, descriptor(contract, b"data"))

    async def seal(self, contract, reservation):
        await self.registry.resolve(contract).write(reservation, b"data")
        async with self.state.leases.writer(reservation):
            return await self.state.catalog.seal(reservation)

    async def failure(self, awaitable, reason):
        with self.assertRaises(SpatialBlobReadError) as failure:
            await awaitable
        self.assertIs(failure.exception.reason, reason)

    async def test_precheck_before_guard_allows_stale_open_after_failed(self):
        """Counterexample for the fixture's proposed check-then-read composition."""
        ref = await self.seal(ROOT_FORMAT, await self.reserve(ROOT_FORMAT))
        target = self.registry.resolve(ROOT_FORMAT)._path(ref)
        checked, resume = asyncio.Event(), asyncio.Event()
        opened = []
        real_open = Path.open

        def observe_open(path, *args, **kwargs):
            stream = real_open(path, *args, **kwargs)
            if path == target:
                opened.append(stream)
            return stream

        with closing(sqlite3.connect(self.bundle[0].path, timeout=0)) as conn:
            store = SQLiteExecutionStore(conn)
            execution = ExecutionId("precheck")
            _, plan = runtime()
            graph = InvocationCoordinator.create(plan, execution, PlanRevision("1"), plan.invocation_root, 16, None).graph
            await store.create(execution, graph.model_dump_json().encode())
            claim = await store.claim(execution, "worker", 60)

            async def checked_read():
                if (await store.load(execution)).status == InvocationStatus.FAILED:
                    raise ValueError("execution closed")
                checked.set()
                await resume.wait()
                return await self.reader.read_root(ref, self.holder)

            with patch.object(Path, "open", observe_open):
                async with asyncio.TaskGroup() as tasks:
                    worker = tasks.create_task(checked_read())
                    try:
                        await asyncio.wait_for(checked.wait(), 5)
                        self.assertFalse(self.bundle[0].conn.in_transaction)
                        graph.failure = "fixture revocation"
                        graph.records[graph.root].status = InvocationStatus.FAILED
                        await store.checkpoint(claim, 0, graph.checkpoint_status(), graph.model_dump_json().encode())
                        self.assertEqual((await store.load(execution)).status, InvocationStatus.FAILED)
                        self.assertTrue(await self.state.holders.is_held(ref, self.holder))
                        with self.assertRaisesRegex(ValueError, "execution closed"):
                            await checked_read()
                        self.assertEqual(len(opened), 0)
                    finally:
                        resume.set()
                self.assertEqual(worker.result(), b"data")
                self.assertEqual(len(opened), 1)
                self.assertTrue(opened[0].closed)

    async def test_admission_and_verified_content(self):
        for contract, read in ((ROOT_FORMAT, self.reader.read_root), (SHARD_FORMAT, self.reader.read_shard)):
            ref = descriptor(contract, b"data")
            await self.failure(read(ref, self.holder), Reason.SOURCE_MISSING)
            reservation = await self.reserve(contract)
            await self.failure(read(ref, self.holder), Reason.SOURCE_UNAVAILABLE)
            await self.seal(contract, reservation)
            foreign = OperationHolder(lease=await self.state.open("other-" + contract.key))
            await self.failure(read(ref, foreign), Reason.SOURCE_UNAVAILABLE)
            self.assertEqual(await read(ref, self.holder, max_bytes=4), b"data")
            await self.failure(read(ref, self.holder, max_bytes=3), Reason.RESOURCE_LIMIT)
            await self.failure(read(ref.model_copy(update={"format_version": 2}), self.holder), Reason.UNSUPPORTED_FORMAT)
            backend = self.registry.resolve(contract)
            path = backend._path(ref)
            path.write_bytes(b"DATA")
            await self.failure(read(ref, self.holder), Reason.SOURCE_CORRUPT)
            path.unlink()
            await self.failure(read(ref, self.holder), Reason.SOURCE_MISSING)

    async def test_profile_and_registry(self):
        ref = descriptor(ROOT_FORMAT, b"data")
        await self.failure(self.reader.read_shard(ref, self.holder), Reason.UNSUPPORTED_FORMAT)
        await self.failure(self.reader.read_root(ref.model_copy(update={"nbytes": ROOT_V1.max_bytes + 1}),
                                                 self.holder, max_bytes=1), Reason.SOURCE_CORRUPT)
        unconfigured = OpenWaterBlobReader(ArtifactFormatRegistryBinding(), self.state.catalog, self.state.holders)
        await self.failure(unconfigured.read_root(ref, self.holder), Reason.SOURCE_UNAVAILABLE)

    async def test_busy_sqlite_guard_maps_to_unavailable(self):
        async with live_database(self.bundle[0].path, seed=False) as second:
            other = SqliteBlobFixture(second)
            await self.bundle[0].conn.execute("PRAGMA busy_timeout=0")
            ref = descriptor(ROOT_FORMAT, b"data")
            async with other.catalog.guard(ref):
                await self.failure(self.reader.read_root(ref, self.holder), Reason.SOURCE_UNAVAILABLE)

    async def test_cancel_retains_sql_guard_until_worker_returns(self):
        ref = await self.seal(ROOT_FORMAT, await self.reserve(ROOT_FORMAT))
        async with live_database(self.bundle[0].path, seed=False) as second:
            other = SqliteBlobFixture(second)
            gc = ArtifactGarbageCollector(self.registry, other.catalog, other.holders, ArtifactLifecycleLog())
            entered, release, competing = threading.Event(), threading.Event(), threading.Event()

            def blocked(path, descriptor):
                entered.set()
                if not release.wait(8):
                    raise TimeoutError("reader was not released")
                return read_verified_file(path, descriptor)

            def trace(statement):
                if statement == "BEGIN IMMEDIATE":
                    competing.set()

            await second[0].conn.set_trace_callback(trace)
            with patch("app.storage.artifacts.blobBackend.read_verified_file", blocked):
                task = asyncio.create_task(self.reader.read_root(ref, self.holder))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                    collect = asyncio.create_task(gc.collect("gc", (ref,)))
                    self.assertTrue(await asyncio.to_thread(competing.wait, 5))
                    task.cancel()
                    await asyncio.sleep(0)
                    self.assertFalse(task.done())
                    self.assertFalse(collect.done())
                    self.assertTrue(self.bundle[0].conn.in_transaction)
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertEqual((await asyncio.wait_for(collect, 5)).retained, (ref,))
