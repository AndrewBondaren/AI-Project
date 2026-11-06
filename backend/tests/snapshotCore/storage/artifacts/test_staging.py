"""Application lifecycle with controlled ports and with SQLite-backed BLOB storage."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, create_autospec, patch

from app.application.artifacts.contracts.formatBackend import ArtifactBackend, ArtifactFormatContract
from app.application.artifacts.contracts.stagingPort import IArtifactStaging
from app.application.artifacts.lifecycle.artifactGc import ArtifactGarbageCollector
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.artifacts.staging.artifactStaging import ArtifactStagingService, TypedArtifactStager
from app.application.publication.contracts.operationStore import IOperationStore
from app.application.publication.errors import OperationBusyError, PublicationInfrastructureError, UnknownCommitOutcome
from app.application.publication.service.operationLedger import OperationLedger
from app.dataModel.artifacts.lifecycle.holders import OperationHolder, ArtifactRetentionHolder
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef, StagingReservation
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord, OperationCancellationReason, OperationCancelled
from app.dataModel.artifacts.references import ArtifactKind, ArtifactFormatRegistry
from app.dataModel.artifacts.events import ArtifactLogActivity
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.registryKey import RegistryKey
from tests.snapshotCore.support.diagnostics import target_issue
from app.storage.artifacts.blobBackend import ContentAddressedBlobBackend
from tests.snapshotCore.support.fakeSection import FakePrepared
from tests.snapshotCore.support.artifactFixtures import adapters, descriptor
from tests.snapshotCore.support.fixtures import live_database, live_started, run_async
from app.db.repositories.sqlite.artifacts.leaseStore import SqliteArtifactLeases


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
        self.terminal = OperationCancelled(operation_id="op", reason=OperationCancellationReason.REQUESTED)
        return self.record(OperationPhase.TERMINAL)


class ArtifactStagingTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[3] / ".tmp_snapshot_core"
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
        self.log.create_gc_failure.side_effect = ArtifactLifecycleLog.create_gc_failure
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
                        from app.dataModel.artifacts.lifecycle.gc import GcFailureStage, GcFailureCode
                        self.assertEqual(report.failed[0].ref, ref)
                        self.assertIs(report.failed[0].stage, GcFailureStage.DELETE)
                        self.assertIs(report.failed[0].code, GcFailureCode.IO_ERROR)
                        self.assertEqual(report.failed[0].message, str(error))
                        self.log.emit_gc_failure.assert_called_once_with(operation_id="op", failure=report.failed[0], cause=error)
                        self.assertEqual(report.deleted, ())
                    else:
                        with self.assertRaises(type(error)):
                            await self.gc.collect("op", (ref,))
                self.assertIn(ref, self.state.sealed)
            with self.assertRaises(ValueError):
                await self.gc.collect("op", (ref, ref))
            self.assertEqual((await self.gc.collect("op", (ref,))).deleted, (ref,))
        run_async(check())

    def test_gc_failure_stages_and_event_admission(self):
        from app.dataModel.artifacts.lifecycle.gc import GcFailureStage

        async def check():
            ref = await self.stager.stage(self.state.lease, b"prepared")
            await self.service.cancel("op", 1)
            for owner, method, stage in (
                (self.registry, "validate", GcFailureStage.VALIDATE),
                (self.state, "read", GcFailureStage.CATALOG_READ),
                (self.state, "holders", GcFailureStage.HOLDERS_READ),
                (self.registry, "delete", GcFailureStage.DELETE),
                (self.state, "mark_deleted", GcFailureStage.MARK_DELETED),
            ):
                with self.subTest(stage=stage), patch.object(owner, method, side_effect=OSError(5, "fault")):
                    report = await self.gc.collect("gc", (ref,))
                    self.assertIs(report.failed[0].stage, stage)
                    self.assertEqual(report.failed[0].errno, 5)
                    self.assertEqual(report.deleted, ())
            for entering in (True, False):
                @asynccontextmanager
                async def guard(candidate):
                    if entering:
                        raise ValueError("enter")
                    yield
                    raise ValueError("exit")
                with patch.object(self.state, "guard", guard):
                    report = await self.gc.collect("gc", (ref,))
                    self.assertIs(report.failed[0].stage,
                                  GcFailureStage.GUARD_ENTER if entering else GcFailureStage.GUARD_EXIT)
                    self.assertEqual(report.deleted, ())
            @asynccontextmanager
            async def unknown_exit(candidate):
                try:
                    yield
                finally:
                    raise UnknownCommitOutcome("exit unknown")
            with patch.object(self.state, "guard", unknown_exit), patch.object(self.registry, "delete", side_effect=OSError("body")):
                with self.assertRaises(UnknownCommitOutcome):
                    await self.gc.collect("gc", (ref,))
            self.log.reset_mock()
            with patch.object(self.registry, "delete", new_callable=AsyncMock) as delete:
                self.log.emit.side_effect = ValueError("event contract")
                with self.assertRaisesRegex(ValueError, "event contract"):
                    await self.gc.collect("gc", (ref,))
                delete.assert_awaited_once()
                self.log.emit_gc_failure.assert_not_called()
            self.log.emit.side_effect = None
            with patch.object(self.registry, "delete", side_effect=OSError("body")):
                self.log.emit_gc_failure.side_effect = ValueError("failure contract")
                with self.assertRaisesRegex(ValueError, "failure contract"):
                    await self.gc.collect("gc", (ref,))
                self.log.emit_gc_failure.assert_called_once()
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
                    diagnostics=(target_issue("refused"),))})
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


class SqliteBlobFixture:
    """Compose production adapters against the fixture database and its BLOB directory."""
    def __init__(self, bundle):
        self.catalog, self.holders = adapters(bundle)
        self.leases = SqliteArtifactLeases(self.catalog._scopes, bundle[-1], bundle[-1]._artifacts)
        contract = ArtifactFormatContract(key=RegistryKey[ArtifactFormatRegistry]("test.blob"),
            kind=ArtifactKind.BLOB, supported_versions=frozenset({1}), content_model=bytes,
            encode=lambda data: data, decode=lambda data, version: data)
        self.backend = ContentAddressedBlobBackend(Path(bundle[0].path).parent / "artifacts", contract, self.leases)
        registry = ArtifactFormatRegistryBinding()
        registry.register(contract, self.backend)
        log = ArtifactLifecycleLog()
        self.ledger = OperationLedger(bundle[-1], self.leases)
        gc = ArtifactGarbageCollector(registry, self.catalog, self.holders, log)
        self.service = ArtifactStagingService(registry, self.catalog, self.leases, self.holders, gc, self.ledger, log)
        self.stager = TypedArtifactStager(contract, 1, registry, self.service)

    async def open(self, op):
        return await self.service.open_operation(op, "w1", OperationKind.PACK_ACTIVATION, "a" * 64)


class SqliteBlobLifecycleTests(unittest.TestCase):
    def test_cancel_drains_repeatedly_cancelled_placement_before_gc(self):
        async def check():
            async with live_database() as first, live_database(first[0].path, seed=False) as second:
                a, b = SqliteBlobFixture(first), SqliteBlobFixture(second)
                lease = await a.open("op")
                ref = descriptor()
                entered, release = threading.Event(), threading.Event()
                place = a.backend._place
                def blocked_place(temp, target):
                    entered.set()
                    if not release.wait(8):
                        raise TimeoutError("placement was never released")
                    place(temp, target)

                with patch.object(a.backend, "_place", blocked_place):
                    stage = asyncio.create_task(a.stager.stage(lease, b"data"))
                    try:
                        async with asyncio.timeout(5):
                            while not entered.is_set():
                                await asyncio.sleep(.002)
                        cancel = asyncio.create_task(b.service.cancel("op", 1))
                        async with asyncio.timeout(5):
                            while True:
                                if cancel.done():
                                    await cancel
                                    self.fail("cancel completed while the placement still held a writer")
                                try:
                                    await a.leases.assert_writable(lease)
                                except ValueError:
                                    break
                                await asyncio.sleep(.002)
                        stage.cancel()
                        await asyncio.sleep(0)
                        stage.cancel()
                        async with second[1].read_scope() as scope:
                            self.assertEqual(len(await b.catalog._writers(scope, "op")), 1)
                        self.assertEqual((await b.service.collect("gc", (ref,))).retained, (ref,))
                        self.assertFalse(cancel.done())
                        self.assertFalse(stage.done())
                    except BaseException:
                        release.set()
                        await asyncio.gather(stage, return_exceptions=True)
                        raise
                    finally:
                        release.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await stage
                result = await asyncio.wait_for(cancel, 5)
                self.assertIsInstance(result.terminal, OperationCancelled)
                self.assertEqual(result.leased_artifacts, ())
                await b.backend.verify(ref)
                self.assertFalse(await b.catalog.is_sealed(ref))
                self.assertEqual((await b.service.collect("gc", (ref,))).deleted, (ref,))
                self.assertFalse(b.backend._path(ref).exists())
        run_async(check())

    def test_gc_serializes_physical_delete_with_reserve_and_restart(self):
        async def check():
            root = Path(__file__).resolve().parents[3] / ".tmp_snapshot_core"
            root.mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=root) as directory:
                path = str(Path(directory) / "test.db")
                async with live_database(path) as first:
                    a = SqliteBlobFixture(first)
                    lease = await a.open("old")
                    ref = await a.stager.stage(lease, b"data")
                    await a.service.finish_preparation(lease, (ref,))
                async with live_database(path, seed=False) as first, live_database(path, seed=False) as second:
                    a, b = SqliteBlobFixture(first), SqliteBlobFixture(second)
                    self.assertEqual((await a.service.recover("old")).phase, OperationPhase.READY)
                    await a.service.verify(ref, OperationHolder(lease=lease))
                    await a.service.cancel("old", 1)
                    new = await b.open("new")
                    deleting, release, reserving = threading.Event(), threading.Event(), threading.Event()
                    sync = a.backend._sync_directory
                    def blocked_sync(parent):
                        deleting.set()
                        if not release.wait(8):
                            raise TimeoutError("delete was never released")
                        sync(parent)
                    gc_boundaries = []
                    def trace_gc(statement):
                        if statement in ("BEGIN IMMEDIATE", "COMMIT", "ROLLBACK"):
                            gc_boundaries.append(statement)

                    def trace_reserve(statement):
                        if statement == "BEGIN IMMEDIATE":
                            reserving.set()
                    with patch.object(a.backend, "_sync_directory", blocked_sync):
                        await first[0].conn.set_trace_callback(trace_gc)
                        await second[0].conn.set_trace_callback(trace_reserve)
                        gc = asyncio.create_task(a.service.collect("gc", (ref,)))
                        try:
                            async with asyncio.timeout(5):
                                while not deleting.is_set():
                                    await asyncio.sleep(.002)
                                reserve = asyncio.create_task(b.service.reserve(new, ref))
                                while not reserving.is_set():
                                    await asyncio.sleep(.002)
                            # Sample A while its filesystem worker is paused and B has entered BEGIN.
                            boundaries_during_delete = tuple(gc_boundaries)
                            gc_transaction_open = first[0].conn.in_transaction
                        finally:
                            release.set()
                        self.assertEqual((await gc).deleted, (ref,))
                        await reserve
                        await first[0].conn.set_trace_callback(None)
                        await second[0].conn.set_trace_callback(None)
                        self.assertEqual(boundaries_during_delete, ("BEGIN IMMEDIATE",))
                        self.assertTrue(gc_transaction_open)
                        self.assertEqual(gc_boundaries, ["BEGIN IMMEDIATE", "COMMIT"])
                async with live_database(path, seed=False) as restarted:
                    c = SqliteBlobFixture(restarted)
                    self.assertFalse(await c.catalog.is_sealed(ref))
                    with self.assertRaises(FileNotFoundError):
                        await c.backend.verify(ref)
                    self.assertTrue(await c.holders.is_held(ref, OperationHolder(lease=new)))
                    self.assertEqual(await c.stager.stage(new, b"data"), ref)
                    await c.service.verify(ref, OperationHolder(lease=new))
        run_async(check())

    def test_ready_inactive_handoff_obeys_outer_rollback_and_retention(self):
        from app.dataModel.worldSnapshot.results.publication import PackActivationDisposition, PackActivationResult

        async def check():
            async with live_database() as first, live_database(first[0].path, seed=False) as second:
                a, b = SqliteBlobFixture(first), SqliteBlobFixture(second)
                active = await live_started(first)
                lease = await a.open("pack")
                ref = await a.stager.stage(lease, b"data")
                manifest = await a.stager.stage(lease, b"manifest")
                await a.service.finish_preparation(lease, (ref, manifest))
                await a.ledger.claim_publication(lease.kind, "pack", "w1", "a" * 64, "b" * 64)
                with self.assertRaises(OperationBusyError):
                    await b.service.recover("pack")
                retained = ArtifactRetentionHolder(artifact=manifest)
                await a.holders.acquire(ref, retained)
                inactive = PackActivationResult(operation_id="pack", request_fingerprint="b" * 64,
                    manifest=manifest, disposition=PackActivationDisposition.READY_INACTIVE, publication=active)
                with self.assertRaisesRegex(RuntimeError, "abort handoff"):
                    async with first[1].transaction("pack") as scope:
                        await a.holders.handoff(scope, lease, (), (ref,))
                        await a.ledger.record_terminal(scope, inactive)
                        raise RuntimeError("abort handoff")
                await b.service.verify(ref, OperationHolder(lease=lease))
                async with first[1].transaction("pack") as scope:
                    await a.holders.handoff(scope, lease, (), (ref,))
                    await a.ledger.record_terminal(scope, inactive)
                self.assertEqual((await b.service.recover("pack")).terminal, inactive)
                self.assertEqual(await b.holders.holders(ref), (retained,))
                self.assertEqual((await b.service.collect("gc", (ref,))).retained, (ref,))
                await b.service.verify(ref, retained)
        run_async(check())

    def test_finish_lost_ack_quarantines_and_fresh_service_observes_durable_state(self):
        async def check(command):
            async with live_database() as first, live_database(first[0].path, seed=False) as second:
                a, b = SqliteBlobFixture(first), SqliteBlobFixture(second)
                lease = await a.open("op")
                ref = await a.stager.stage(lease, b"data")
                driver = first[1].driver
                settle = getattr(driver, command)
                async def lose_ack(conn):
                    await settle(conn)
                    raise OSError("ack lost")
                with patch.object(driver, command, lose_ack):
                    with self.assertRaises(UnknownCommitOutcome):
                        await a.service.finish_preparation(lease, (ref,) if command == "commit" else ())
                with self.assertRaises(UnknownCommitOutcome):
                    await a.service.recover("op")
                recovered = await b.service.recover("op")
                self.assertEqual(recovered.phase, OperationPhase.READY if command == "commit" else OperationPhase.PREPARING)
                self.assertEqual(recovered.leased_artifacts, (ref,))
                await b.service.verify(ref, OperationHolder(lease=lease))
        for command in ("commit", "rollback"):
            with self.subTest(command=command):
                run_async(check(command))

    def test_recover_preserves_persisted_writer_and_cannot_take_over_publication(self):
        from app.db.models.snapshotCore.operationRows import PublicationOperationEventRow
        from tests.snapshotCore.support.artifactFixtures import writer_fact

        async def check():
            async with live_database() as first:
                a = SqliteBlobFixture(first)
                writer_lease = await a.open("writer")
                reservation = await a.service.reserve(writer_lease, descriptor())
                # Only the acquire is persisted. Recovery has no proof that its worker stopped.
                await writer_fact(first, reservation)
                lease = await a.open("publication")
                ref = await a.stager.stage(lease, b"prepared")
                await a.service.finish_preparation(lease, (ref,))
                await a.ledger.claim_publication(lease.kind, "publication", "w1", "a" * 64, "b" * 64)
                async with first[1].transaction("publication") as scope:
                    event = await first[-1]._event("publication", scope)
                    await first[2]._access.insert(scope, PublicationOperationEventRow("recovery", "publication",
                        event.event_id, event.event_seq + 1, "recovery_required", lease.fence))
                async with live_database(first[0].path, seed=False) as second:
                    b = SqliteBlobFixture(second)
                    waiting = await b.service.recover("writer")
                    self.assertEqual((waiting.phase, waiting.fence, waiting.leased_artifacts),
                        (OperationPhase.PREPARING, writer_lease.fence, (reservation.ref,)))
                    async with second[1].read_scope() as scope:
                        self.assertEqual(len(await b.catalog._writers(scope, "writer")), 1)
                    with self.assertRaises(OperationBusyError):
                        await b.service.recover("publication")
                    record = await a.ledger.read("publication")
                    self.assertEqual((record.phase, record.fence, record.leased_artifacts),
                        (OperationPhase.RECOVERY_REQUIRED, lease.fence, (ref,)))
                    await b.service.verify(ref, OperationHolder(lease=lease))
        run_async(check())
