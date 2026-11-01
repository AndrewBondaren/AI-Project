"""Physical bytes tests with controlled lifecycle admission, independent of SQL review."""

import asyncio
from contextlib import asynccontextmanager
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.references import ArtifactKind, ArtifactRef, ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from tests.snapshotCore.support.fixtures import run_async


class Admission:
    def __init__(self):
        self.active = 0
        self.writable = True
        self.checks = 0

    @asynccontextmanager
    async def writer(self, reservation):
        self.active += 1
        try:
            await self.assert_writable(reservation.lease)
            yield
        finally:
            self.active -= 1

    async def assert_writable(self, lease):
        self.checks += 1
        if not self.writable:
            raise ValueError("stale fence")


class BlobBackendTests(unittest.TestCase):
    def setUp(self):
        temporary_root = Path(__file__).resolve().parents[4] / ".tmp_snapshot_core"
        temporary_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "artifacts"
        self.admission = Admission()
        self.contract = ArtifactFormatContract(
            key=RegistryKey[ArtifactFormatRegistry]("test.blob"), kind=ArtifactKind.BLOB,
            supported_versions=frozenset({1}), content_model=bytes, encode=lambda data: data,
            decode=lambda data, version: data)
        self.backend = ContentAddressedBlobBackend(self.root, self.contract, self.admission)
        self.data = b"immutable content"
        self.ref = ArtifactRef(kind=ArtifactKind.BLOB, format_key=self.contract.key, format_version=1,
            content_hash=hashlib.sha256(self.data).hexdigest(), nbytes=len(self.data), row_count=None)
        self.reservation = StagingReservation(artifact_id="artifact", ref=self.ref,
            lease=OperationLeaseRef(operation_id="op", world_uid="world", kind=OperationKind.SNAPSHOT_APPLY,
                                    preparation_fingerprint="a" * 64, fence=1))

    def test_dedupe_verify_delete_and_restart(self):
        async def check():
            await self.backend.write(self.reservation, self.data)
            path = self.backend._path(self.ref)
            before = path.stat().st_mtime_ns
            other = self.reservation.model_copy(update={"artifact_id": "other",
                "lease": self.reservation.lease.model_copy(update={"operation_id": "other"})})
            await asyncio.gather(self.backend.write(self.reservation, self.data), self.backend.write(other, self.data))
            self.assertEqual(path.stat().st_mtime_ns, before)
            restart = ContentAddressedBlobBackend(self.root, self.contract, self.admission)
            await restart.verify(self.ref)
            self.assertEqual(list(path.parent.glob(".tmp-*")), [])
            await restart.delete(self.ref)
            await restart.delete(self.ref)
            with self.assertRaises(FileNotFoundError):
                await restart.verify(self.ref)
        run_async(check())

    def test_missing_corrupt_existing_hash_and_wrong_descriptor(self):
        async def check():
            with self.assertRaises(FileNotFoundError):
                await self.backend.verify(self.ref)
            with self.assertRaises(ValueError):
                await self.backend.write(self.reservation, b"wrong")
            await self.backend.write(self.reservation, self.data)
            path = self.backend._path(self.ref)
            path.write_bytes(b"x" * len(self.data))
            with self.assertRaises(PublicationInfrastructureError):
                await self.backend.verify(self.ref)
            with self.assertRaises(PublicationInfrastructureError):
                await self.backend.write(self.reservation, self.data)
            self.assertEqual(path.read_bytes(), b"x" * len(self.data))
            self.assertEqual(list(path.parent.glob(".tmp-*")), [])
            for changes in ({"format_version": 2}, {"format_key": "other.blob"}, {"nbytes": True}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    await self.backend.verify(self.ref.model_copy(update=changes))
        run_async(check())

    def test_stale_fence_and_failure_before_and_after_placement(self):
        async def check():
            self.admission.writable = False
            with self.assertRaises(ValueError):
                await self.backend.write(self.reservation, self.data)
            self.assertFalse(self.root.exists())
            self.admission.writable = True
            with patch.object(self.backend, "_place", side_effect=OSError("before placement")):
                with self.assertRaises(OSError):
                    await self.backend.write(self.reservation, self.data)
            self.assertFalse(self.backend._path(self.ref).exists())
            place = self.backend._place
            def fail_after(temp, ref):
                place(temp, ref)
                raise OSError("after placement")
            with patch.object(self.backend, "_place", side_effect=fail_after):
                with self.assertRaises(OSError):
                    await self.backend.write(self.reservation, self.data)
            await self.backend.verify(self.ref)
            self.assertEqual(self.admission.active, 0)
            await self.backend.write(self.reservation, self.data)
        run_async(check())

    def test_fence_recheck_and_fsync_failure_leave_no_final_or_temp(self):
        async def check():
            prepare = self.backend._temp
            def invalidate(*args):
                temp = prepare(*args)
                self.admission.writable = False
                return temp
            with patch.object(self.backend, "_temp", side_effect=invalidate):
                with self.assertRaises(ValueError):
                    await self.backend.write(self.reservation, self.data)
            self.assertFalse(self.backend._path(self.ref).exists())
            self.assertEqual(list(self.root.rglob(".tmp-*")), [])
            self.admission.writable = True
            with patch("app.storage.artifacts.blobBackend.os.fsync", side_effect=OSError("flush failed")):
                with self.assertRaises(OSError):
                    await self.backend.write(self.reservation, self.data)
            self.assertFalse(self.backend._path(self.ref).exists())
            self.assertEqual(list(self.root.rglob(".tmp-*")), [])
            self.assertEqual(self.admission.active, 0)
        run_async(check())

    def test_cancellation_drains_worker_before_releasing_claim(self):
        async def check(after):
            entered, release = threading.Event(), threading.Event()
            original = self.backend._place if after else self.backend._temp
            def blocked(*args):
                result = original(*args)
                entered.set()
                if not release.wait(10):
                    raise TimeoutError("test worker was not released")
                return result
            with patch.object(self.backend, "_place" if after else "_temp", side_effect=blocked):
                task = asyncio.create_task(self.backend.write(self.reservation, self.data))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 10))
                    task.cancel()
                    await asyncio.sleep(0)
                    self.assertEqual(self.admission.active, 1)
                    task.cancel()  # Repeated cancellation must also drain.
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertEqual(self.admission.active, 0)
            self.assertEqual(self.backend._path(self.ref).exists(), after)
            self.assertEqual(list(self.root.rglob(".tmp-*")), [])
        run_async(check(False))
        run_async(check(True))

    def test_path_escape_and_unsafe_root_are_rejected(self):
        with self.assertRaises(ValueError):
            ContentAddressedBlobBackend(Path("relative"), self.contract, self.admission)
        with self.assertRaises(ValueError):
            run_async(self.backend.verify(self.ref.model_copy(update={"content_hash": "../escape"})))

    def test_symlink_escape_is_rejected(self):
        self.root.mkdir()
        namespace = self.backend._path(self.ref).parent
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            namespace.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink privilege unavailable on this Windows host")
        with self.assertRaises(PublicationInfrastructureError):
            run_async(self.backend.write(self.reservation, self.data))
