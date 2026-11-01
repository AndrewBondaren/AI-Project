"""Application lifecycle tests; controlled storage ports plus the real BLOB backend."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, create_autospec, patch

from app.application.artifacts.contracts.formatBackend import ArtifactBackend, ArtifactFormatContract
from app.application.artifacts.contracts.stagingPort import IArtifactStaging
from app.application.artifacts.lifecycle.artifactGc import ArtifactGarbageCollector
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.staging.artifactStaging import ArtifactStagingService, TypedArtifactStager
from app.application.publication.contracts.operationStore import IOperationStore
from app.application.publication.errors import PublicationInfrastructureError, UnknownCommitOutcome
from app.application.publication.service.operationLedger import OperationLedger
from app.dataModel.artifacts.lifecycle.holders import OperationHolder, ArtifactRetentionHolder
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord, OperationCancelled
from app.dataModel.artifacts.references import ArtifactKind, ArtifactFormatRegistry
from app.dataModel.artifacts.events import ArtifactLogActivity
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from tests.snapshotCore.support.fakeSection import FakePrepared
from tests.snapshotCore.support.fixtures import run_async


class LifecycleFixture:
    """Model the required guard/hold/claim contract, without claiming SQL evidence."""
    def __init__(self):
        self.lease = OperationLeaseRef(operation_id="op", world_uid="world", kind=OperationKind.PACK_ACTIVATION,
                                      preparation_fingerprint="a" * 64, fence=1)
        self.refs, self.holds, self.sealed = {}, {}, set()
        self.locks = {}
        self.active, self.closed, self.terminal = 0, False, None
        self.drained = asyncio.Event()
        self.drained.set()

    def guard(self, ref):
        return self.locks.setdefault(ref, asyncio.Lock())

    async def read(self, ref):
        return self.refs.get(ref)

    async def reserve(self, lease, descriptor):
        async with self.guard(descriptor):
            await self.assert_writable(lease)
            self.refs[descriptor] = descriptor
            self.holds.setdefault(descriptor, set()).add(OperationHolder(lease=lease))
            return StagingReservation(artifact_id="artifact", lease=lease, ref=descriptor)

    async def seal(self, reservation):
        async with self.guard(reservation.ref):
            await self.assert_writable(reservation.lease)
            if self.active != 1:
                raise AssertionError("seal needs exactly one claim")
            self.sealed.add(reservation.ref)
            return reservation.ref

    async def is_sealed(self, ref):
        return ref in self.sealed

    async def mark_deleted(self, ref):
        if self.holds.get(ref) or self.active:
            raise AssertionError("cannot delete protected content")
        self.sealed.discard(ref)

    async def holders(self, ref):
        return tuple(self.holds.get(ref, ()))

    async def is_held(self, ref, holder):
        return holder in self.holds.get(ref, ())

    async def assert_writable(self, lease):
        if self.closed or lease != self.lease:
            raise ValueError("closed or stale lease")

    @asynccontextmanager
    async def writer(self, reservation):
        await self.assert_writable(reservation.lease)
        if not await self.is_held(reservation.ref, OperationHolder(lease=reservation.lease)):
            raise ValueError("writer has no operation hold")
        self.active += 1
        self.drained.clear()
        try:
            yield
        finally:
            self.active -= 1
            if not self.active:
                self.drained.set()

    def record(self, phase=OperationPhase.PREPARING):
        return OperationRecord(operation_id="op", world_uid="world", kind=self.lease.kind,
            preparation_fingerprint="a" * 64, publication_fingerprint=None, phase=phase,
            fence=1, leased_artifacts=tuple(self.refs), terminal=self.terminal)

    async def open_operation(self, *args):
        return self.lease

    async def finish_preparation(self, lease, refs):
        await self.assert_writable(lease)
        if self.active or set(refs) != self.sealed:
            raise ValueError("incomplete preparation")
        self.closed = True
        return self.record(OperationPhase.READY)

    async def recover(self, operation_id):
        return self.record()

    async def cancel(self, operation_id, fence):
        if fence != self.lease.fence:
            raise ValueError("stale fence")
        self.closed = True
        await self.drained.wait()
        for holders in self.holds.values():
            holders.discard(OperationHolder(lease=self.lease))
        self.terminal = OperationCancelled(operation_id="op", reason=FieldPathError(path=(), message="cancelled"))
        return self.record(OperationPhase.TERMINAL)


class ArtifactStagingTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[4] / ".tmp_snapshot_core"
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.state = LifecycleFixture()
        self.contract = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.blob"),
            kind=ArtifactKind.BLOB, supported_versions=frozenset({1}), content_model=bytes,
            encode=lambda content: content, decode=lambda data, version: data)
        self.backend = ContentAddressedBlobBackend(Path(self.temp.name) / "artifacts", self.contract, self.state)
        self.registry = ArtifactFormatRegistryBinding()
        self.registry.register(self.contract, self.backend)
        self.operations = create_autospec(IOperationStore, instance=True)
        self.operations.read.return_value = None
        self.ledger = OperationLedger(self.operations, self.state)
        self.log = create_autospec(ArtifactLifecycleLog, instance=True)
        self.gc = ArtifactGarbageCollector(self.registry, self.state, self.state, self.log)
        self.service = ArtifactStagingService(self.registry, self.state, self.state, self.state,
                                             self.gc, self.ledger, self.log)
        self.stager = TypedArtifactStager(self.contract, 1, self.registry, self.service)

    def test_stage_finish_and_ready_inactive_retention(self):
        async def check():
            ref = await self.stager.stage(self.state.lease, b"prepared")
            holder = OperationHolder(lease=self.state.lease)
            self.assertEqual((await self.service.verify(ref, holder)).ref, ref)
            self.assertEqual((await self.service.finish_preparation(self.state.lease, (ref,))).phase, OperationPhase.READY)
            self.assertFalse(any(call.args[0].activity is ArtifactLogActivity.LEASE_RELEASED
                                 for call in self.log.emit.call_args_list))
            # A ready_inactive pack keeps an artifact retention hold after cancellation.
            retained = ArtifactRetentionHolder(artifact=ref)
            self.state.holds[ref].add(retained)
            await self.service.cancel("op", 1)
            self.assertEqual((await self.service.collect("op", (ref,))).retained, (ref,))
            await self.backend.verify(ref)
        run_async(check())

    def test_failure_before_seal_recovery_needs_no_prepared_content(self):
        async def check():
            with patch.object(self.state, "seal", side_effect=OSError("before seal")):
                with self.assertRaises(OSError):
                    await self.stager.stage(self.state.lease, b"prepared")
            ref = next(iter(self.state.refs))
            self.assertFalse(await self.state.is_sealed(ref))
            self.assertEqual((await self.service.collect("op", (ref,))).retained, (ref,))
            self.assertEqual((await self.service.recover("op")).leased_artifacts, (ref,))
            # Recreate application facade; durable bytes + reservation suffice for seal.
            restarted = ArtifactStagingService(self.registry, self.state, self.state, self.state,
                                                self.gc, self.ledger, self.log)
            reservation = StagingReservation(artifact_id="artifact", lease=self.state.lease, ref=ref)
            self.assertEqual(await restarted.seal(reservation), ref)
        run_async(check())

    def test_failure_after_seal_retries_immutably(self):
        async def check():
            seal = self.state.seal
            async def lost_ack(reservation):
                await seal(reservation)
                raise OSError("response lost after seal")
            with patch.object(self.state, "seal", side_effect=lost_ack):
                with self.assertRaises(OSError):
                    await self.stager.stage(self.state.lease, b"prepared")
            ref = next(iter(self.state.sealed))
            self.assertEqual(await self.stager.stage(self.state.lease, b"prepared"), ref)
            self.assertEqual(self.state.active, 0)
        run_async(check())

    def test_cancel_drains_claim_and_gc_retains_until_release(self):
        async def check():
            ref = await self.stager.stage(self.state.lease, b"prepared")
            reservation = StagingReservation(artifact_id="artifact", lease=self.state.lease, ref=ref)
            entered, release = asyncio.Event(), asyncio.Event()
            async def writer():
                async with self.state.writer(reservation):
                    entered.set()
                    await release.wait()
            writing = asyncio.create_task(writer())
            await entered.wait()
            cancelling = asyncio.create_task(self.service.cancel("op", 1))
            await asyncio.sleep(0)
            self.assertFalse(cancelling.done())
            self.assertFalse(any(call.args[0].activity is ArtifactLogActivity.LEASE_RELEASED
                                 for call in self.log.emit.call_args_list))
            self.assertEqual((await self.gc.collect("op", (ref,))).retained, (ref,))
            release.set()
            await writing
            await cancelling
            released = [call.args[0] for call in self.log.emit.call_args_list
                        if call.args[0].activity is ArtifactLogActivity.LEASE_RELEASED]
            self.assertEqual(len(released), 1)
            self.assertEqual((released[0].operation_id, released[0].world_uid,
                              released[0].preparation_fingerprint, released[0].request_fingerprint,
                              released[0].artifact_hash), ("op", "world", "a" * 64, None, None))
            self.assertEqual((await self.gc.collect("op", (ref,))).deleted, (ref,))
            self.assertEqual((await self.gc.collect("op", (ref,))).deleted, (ref,))
            with self.assertRaises(FileNotFoundError):
                await self.backend.verify(ref)
        run_async(check())

    def test_corruption_unheld_ref_and_unknown_format_are_refused(self):
        async def check():
            ref = await self.stager.stage(self.state.lease, b"prepared")
            self.backend._path(ref).write_bytes(b"corrupt")
            with self.assertRaises(PublicationInfrastructureError):
                await self.service.verify(ref, OperationHolder(lease=self.state.lease))
            unknown = ref.model_copy(update={"format_key": RegistryKey[ArtifactFormatRegistry]("unknown")})
            with self.assertRaises(ValueError):
                await self.service.reserve(self.state.lease, unknown)
            self.state.holds[ref].clear()
            with self.assertRaises(ValueError):
                await self.service.verify(ref, OperationHolder(lease=self.state.lease))
        run_async(check())

    def test_sql_row_count_is_owned_by_format_binding(self):
        async def check():
            def contract(count):
                return ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.rows"),
                    kind=ArtifactKind.SQL_ROWS, supported_versions=frozenset({1}), content_model=FakePrepared,
                    encode=lambda value: value.model_dump_json().encode(),
                    decode=lambda data, version: FakePrepared.model_validate_json(data), row_count=count)
            with self.assertRaises(TypeError):
                contract(None)
            for count in (lambda value: True, lambda value: -1, lambda value: None, lambda value: len(value.values)):
                binding = contract(count)
                backend = create_autospec(ArtifactBackend, instance=True)
                backend.contract = binding
                registry = ArtifactFormatRegistryBinding()
                registry.register(binding, backend)
                staging = create_autospec(IArtifactStaging, instance=True)
                async def reserve(lease, ref):
                    return StagingReservation(artifact_id="rows", lease=lease, ref=ref)
                staging.reserve.side_effect = reserve
                staging.seal.side_effect = lambda reservation: reservation.ref
                stager = TypedArtifactStager(binding, 1, registry, staging)
                content = FakePrepared(values=(1, 2))
                if count(content) == 2:
                    self.assertEqual((await stager.stage(self.state.lease, content)).row_count, 2)
                else:
                    with self.assertRaises(ValueError):
                        await stager.stage(self.state.lease, content)
                    staging.reserve.assert_not_awaited()
            with self.assertRaises(TypeError):
                replace(self.contract, row_count=lambda value: 0)
        run_async(check())

    def test_gc_io_failure_cancellation_and_uncertainty(self):
        async def check():
            ref = await self.stager.stage(self.state.lease, b"prepared")
            await self.service.cancel("op", 1)
            for error in (OSError("IO"), asyncio.CancelledError(), UnknownCommitOutcome("unknown")):
                with patch.object(self.registry, "delete", side_effect=error):
                    if isinstance(error, OSError):
                        report = await self.gc.collect("op", (ref,))
                        self.assertEqual(len(report.failed), 1)
                        self.assertEqual(report.deleted, ())
                    else:
                        with self.assertRaises(type(error)):
                            await self.gc.collect("op", (ref,))
                self.assertIn(ref, self.state.sealed)
            with self.assertRaises(ValueError):
                await self.gc.collect("op", (ref, ref))
        run_async(check())

    def test_terminal_recovery_does_not_resume_or_republish(self):
        async def check():
            terminal = await self.state.cancel("op", 1)
            self.operations.read.return_value = terminal
            with patch.object(self.state, "recover", new_callable=AsyncMock) as recover:
                self.assertEqual(await self.ledger.recover("op"), terminal)
                recover.assert_not_awaited()
            for fence in (True, 0, -1):
                with self.assertRaises(ValueError):
                    await self.ledger.cancel("op", fence)
        run_async(check())

    def test_release_logging_requires_confirmed_matching_cancellation(self):
        async def check():
            for error in (ValueError("stale"), asyncio.CancelledError(), UnknownCommitOutcome("unknown")):
                with patch.object(self.ledger, "cancel", side_effect=error):
                    with self.assertRaises(type(error)):
                        await self.service.cancel("op", 1)
                self.log.emit.assert_not_called()
            # A non-cancelled observation does not assert a release.
            with patch.object(self.ledger, "cancel", return_value=self.state.record()):
                await self.service.cancel("op", 1)
            self.log.emit.assert_not_called()
            terminal = await self.state.cancel("op", 1)
            refusal = terminal.model_copy(update={"publication_fingerprint": "b" * 64,
                "terminal": SnapshotApplyResult(operation_id="op", request_fingerprint="b" * 64,
                    category=SnapshotApplyOutcomeKind.REJECTED, committed=None,
                    diagnostics=(FieldPathError(path=(), message="refused"),))})
            with patch.object(self.ledger, "cancel", return_value=refusal):
                await self.service.cancel("op", 1)
            self.log.emit.assert_not_called()
            for changes in ({"fence": 2}, {"operation_id": "other", "terminal":
                    OperationCancelled(operation_id="other", reason=terminal.terminal.reason)}):
                mismatch = terminal.model_copy(update=changes)
                with patch.object(self.ledger, "cancel", return_value=mismatch):
                    with self.assertRaises(PublicationInfrastructureError):
                        await self.service.cancel("op", 1)
                self.log.emit.assert_not_called()
            self.operations.read.return_value = terminal
            await self.service.recover("op")
            self.log.emit.assert_not_called()
            await self.service.cancel("op", 1)
            self.assertEqual(self.log.emit.call_args.args[0].activity, ArtifactLogActivity.LEASE_RELEASED)
        run_async(check())

    def test_release_logging_sink_failure_preserves_cancelled_result(self):
        async def check():
            self.service._log = ArtifactLifecycleLog()
            with patch("app.application.artifacts.logging.artifactLog._LOGGER.log", side_effect=OSError("sink")):
                result = await self.service.cancel("op", 1)
            self.assertIsInstance(result.terminal, OperationCancelled)
            self.assertEqual(result.phase, OperationPhase.TERMINAL)
        run_async(check())
