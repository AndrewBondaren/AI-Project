"""P2R-B through the public reader, real SQLite guard/holders and file backend."""
import asyncio
import threading
from pathlib import Path
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from app.application.artifacts.lifecycle.artifactGc import ArtifactGarbageCollector
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.worldData.generators.hydrology.encoding.packFormats import ROOT_FORMAT, SHARD_FORMAT
from app.application.worldData.pack.spatial.openWaterBlobReader import OpenWaterBlobReader, SpatialBlobReadError
from app.dataModel.artifacts.lifecycle.holders import OperationHolder
from app.dataModel.hydrology.pack.profile import ROOT_V1
from app.dataModel.spatial.readFailureReason import SpatialReadFailureReason as Reason
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from app.storage.artifacts.blobRead import read_verified_file
from tests.snapshotCore.storage.artifacts.test_staging import SqliteBlobFixture
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
