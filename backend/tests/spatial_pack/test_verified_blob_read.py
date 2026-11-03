"""Physical root/shard read, byte bounds and lifetime of the worker."""
import asyncio
import hashlib
import io
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldData.generators.hydrology.encoding.packCodec import (
    decode_root, decode_shard, encode_root, encode_shard,
)
from app.application.worldData.generators.hydrology.encoding.packFormats import ROOT_FORMAT, SHARD_FORMAT
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef
from app.dataModel.hydrology.pack.profile import ROOT_V1, SHARD_V1
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from tests.snapshotCore.storage.artifacts.test_blob_backend import Admission
from tests.spatial_pack.test_storage_schema import records


def descriptor(contract, data):
    return ArtifactRef(kind=ArtifactKind.BLOB, format_key=contract.key, format_version=1,
                       content_hash=hashlib.sha256(data).hexdigest(), nbytes=len(data))


class RunnerShutdownTests(TestCase):
    def test_shutdown_cancels_read_only_after_file_is_closed(self):
        entered, release = threading.Event(), threading.Event()
        observed = []

        class Blocking(io.BytesIO):
            def read(stream, size):
                entered.set()
                if not release.wait(5):
                    raise AssertionError("worker did not receive release")
                return super().read(size)

        stream = Blocking(b"x")
        backend = ContentAddressedBlobBackend(Path.cwd(), ROOT_FORMAT, Admission())

        async def read():
            try:
                await backend.read_verified(descriptor(ROOT_FORMAT, b"x"), max_bytes=1)
            except asyncio.CancelledError:
                observed.append(stream.closed)
                raise

        async def main():
            task = asyncio.create_task(read())
            self.assertTrue(await asyncio.to_thread(entered.wait, 5))
            # main returns with the read pending; the runner cancels all tasks.
            asyncio.get_running_loop().call_later(0.1, release.set)
            return task

        with patch.object(Path, "open", return_value=stream):
            task = asyncio.run(main())
        self.assertTrue(task.cancelled())
        self.assertEqual(observed, [True])


class VerifiedReadTests(IsolatedAsyncioTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.backend = ContentAddressedBlobBackend(self.directory, ROOT_FORMAT, Admission())

    async def test_restart_reads_real_root_and_shard(self):
        root, shard = records()
        lease = OperationLeaseRef(operation_id="op", world_uid="world", kind=OperationKind.SNAPSHOT_APPLY,
                                  preparation_fingerprint="a" * 64, fence=1)
        for record, contract, cap, encode, decode in (
                (root, ROOT_FORMAT, ROOT_V1.max_bytes, encode_root, decode_root),
                (shard, SHARD_FORMAT, SHARD_V1.max_bytes, encode_shard, decode_shard)):
            data = encode(record)
            ref = descriptor(contract, data)
            writer = ContentAddressedBlobBackend(self.directory, contract, Admission())
            await writer.write(StagingReservation(artifact_id="artifact", ref=ref, lease=lease), data)
            reader = ContentAddressedBlobBackend(self.directory, contract, Admission())
            result = await reader.read_verified(ref, max_bytes=cap)
            self.assertEqual(result, data)
            self.assertEqual(decode(result, 1), record)

    async def test_refused_before_open(self):
        ref = descriptor(ROOT_FORMAT, b"ab")
        with patch.object(Path, "open", side_effect=AssertionError):
            for candidate, cap in ((ref, 1), (ref, True), (descriptor(SHARD_FORMAT, b"x"), 1),
                                   (ref.model_copy(update={"format_version": 2}), 2),
                                   (descriptor(ROOT_FORMAT, b""), 1)):
                with self.assertRaises(ValueError):
                    await self.backend.read_verified(candidate, max_bytes=cap)

    async def test_bounded_single_open_and_close(self):
        class Counted(io.BytesIO):
            def close(stream):
                stream.consumed = stream.tell()
                super().close()

        ref = descriptor(ROOT_FORMAT, b"ab")
        for data, consumed in ((b"a", 1), (b"ax", 2), (b"ab" * 4096, 3)):
            stream = Counted(data)
            with patch.object(Path, "open", return_value=stream) as opened, self.assertRaises(PublicationInfrastructureError):
                await self.backend.read_verified(ref, max_bytes=2)
            opened.assert_called_once_with("rb", buffering=0)
            self.assertTrue(stream.closed)
            self.assertEqual(stream.consumed, consumed)
        with self.assertRaises(PublicationInfrastructureError) as missing:
            await self.backend.read_verified(ref, max_bytes=2)
        self.assertIsInstance(missing.exception.__cause__, FileNotFoundError)

    async def test_cancel_drains_open_file(self):
        entered, release = threading.Event(), threading.Event()

        class Blocking(io.BytesIO):
            def read(stream, size):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("test did not release reader")
                return super().read(size)

        stream = Blocking(b"x")
        with patch.object(Path, "open", return_value=stream):
            task = asyncio.create_task(self.backend.read_verified(descriptor(ROOT_FORMAT, b"x"), max_bytes=1))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 5))
                task.cancel()
                await asyncio.sleep(0)
                self.assertFalse(task.done())
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(stream.closed)
