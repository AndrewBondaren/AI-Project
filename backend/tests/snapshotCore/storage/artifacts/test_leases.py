"""DDL lease/writer/fence invariants; actual shared guards belong to 4C3."""

import sqlite3
import unittest
from tests.snapshotCore.support.fixtures import new_database, stage, close_writers, insert, operation
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.lifecycle.holders import OperationHolder
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.db.models.artifacts.leaseRows import ArtifactLeaseEventRow
from app.db.models.snapshotCore.operationRows import PublicationOperationEventRow
from tests.snapshotCore.support.fixtures import live_database, run_async, unsafe_update
from tests.snapshotCore.support.artifactFixtures import adapters, descriptor, preparing, sealed, close_preparation, writer_fact


class ArtifactLeaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = new_database()
        self.addCleanup(self.conn.close)

    def test_ready_requires_closed_drained_writers_and_later_writes_are_refused(self):
        descriptor, hold, claim, storage = stage(self.conn)
        ready = dict(event_id="ready", operation_id="stage", predecessor_id="stage-event", event_seq=2, phase="ready", fence=1)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "publication_operation_events", **ready)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_holder_events", **{**hold, "event_id": "release", "predecessor_id": hold["event_id"],
                   "event_seq": 2, "event_kind": "release"})
        close_writers(self.conn)
        insert(self.conn, "publication_operation_events", **ready)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_writer_claims", **{**claim, "event_id": "late", "predecessor_id": "stage-writer-release", "event_seq": 3})
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_lease_events", event_id="reopen", operation_id="stage", predecessor_id="stage-closed",
                   event_seq=3, fence=1, admission_open=1)

    def test_recovery_uses_new_fence_and_old_attempt_cannot_acquire_a_hold(self):
        operation(self.conn, "recover")
        insert(self.conn, "publication_operation_events", event_id="recovery", operation_id="recover",
               predecessor_id="recover-event", event_seq=2, phase="recovery_required", fence=1)
        insert(self.conn, "publication_operation_events", event_id="ready", operation_id="recover",
               predecessor_id="recovery", event_seq=3, phase="ready", fence=2)
        descriptor, hold, claim, storage = stage(self.conn)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_holder_events", **{**hold, "event_id": "stale", "operation_id": "recover"})
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_writer_claims", **{**claim, "event_id": "stale", "operation_id": "recover"})

    def test_lease_and_writer_chains_reject_wrong_owners_and_invalid_sequences(self):
        descriptor, hold, claim, storage = stage(self.conn)
        operation(self.conn, "other", phase="preparing", bound=False)
        for changes in ({"operation_id": "other"}, {"fence": 2}, {"event_seq": 4}, {"event_kind": "acquire"}):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "artifact_writer_claims", **{**claim, "event_id": "bad", "predecessor_id": claim["event_id"],
                       "event_seq": 2, "event_kind": "release", **changes})

    def test_cancellation_requires_closed_admission_and_drained_claims(self):
        stage(self.conn)
        cancelled = dict(operation_id="stage", outcome_kind="cancelled", category=None,
                         format_version=1, outcome_data=b"cancelled", outcome_checksum="c" * 64)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "publication_outcomes", **cancelled)
        insert(self.conn, "artifact_lease_events", event_id="stage-closed", operation_id="stage",
               predecessor_id="stage-lease", event_seq=2, fence=1, admission_open=0)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "publication_outcomes", **cancelled)
        insert(self.conn, "artifact_writer_claims", event_id="stage-writer-release", artifact_id="artifact",
               operation_id="stage", fence=1, predecessor_id="stage-writer", event_seq=2, event_kind="release")
        insert(self.conn, "publication_outcomes", **cancelled)


class ArtifactAdmissionReadTests(unittest.TestCase):
    def test_catalog_checks_lease_and_writer_row_boundaries_without_a_lease_adapter(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                reservation = await catalog.reserve(lease, descriptor())
                await writer_fact(bundle, reservation)
                async with bundle[1].read_scope() as scope:
                    writer = (await catalog._writers(scope, artifact_id=reservation.artifact_id))[0]
                for column, bad in {"event_id": " bad ", "artifact_id": " bad ", "operation_id": " bad ",
                        "fence": 0, "predecessor_id": "missing", "event_seq": 0, "event_kind": "unknown"}.items():
                    with self.subTest(table="writer", column=column):
                        old = await unsafe_update(bundle[0], "artifact_writer_claims", "event_id", writer.event_id, column, bad)
                        try:
                            async with bundle[1].read_scope() as scope:
                                with self.assertRaises(PublicationInfrastructureError):
                                    await catalog._writers(scope)
                        finally:
                            await unsafe_update(bundle[0], "artifact_writer_claims", "event_id",
                                bad if column == "event_id" else writer.event_id, column, old)
                for column, bad in {"event_id": " bad ", "operation_id": "missing", "predecessor_id": "missing",
                        "event_seq": 0, "fence": 0, "admission_open": 2}.items():
                    with self.subTest(table="lease", column=column):
                        old = await unsafe_update(bundle[0], "artifact_lease_events", "event_id", lease.operation_id + "-lease", column, bad)
                        try:
                            with self.assertRaises((PublicationInfrastructureError, ValueError)):
                                await catalog.reserve(lease, descriptor("must not reserve"))
                            if column == "operation_id":
                                with self.assertRaises(ValueError):
                                    await holders.release(reservation.ref, OperationHolder(lease=lease))
                        finally:
                            await unsafe_update(bundle[0], "artifact_lease_events", "event_id",
                                bad if column == "event_id" else lease.operation_id + "-lease", column, old)
        run_async(check())

    def test_historical_holder_fence_is_not_replaced_by_current_operation_fence(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                ref = descriptor()
                await sealed(bundle, catalog, lease, ref)
                await close_preparation(bundle, lease, ready=True)
                await bundle[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, lease.operation_id, "w1", "a" * 64, "b" * 64)
                async with bundle[1].transaction(lease.operation_id) as scope:
                    event = await bundle[-1]._event(lease.operation_id, scope)
                    await bundle[2]._access.insert(scope, PublicationOperationEventRow("recover", lease.operation_id,
                        event.event_id, event.event_seq + 1, "recovery_required", 1))
                    await bundle[2]._access.insert(scope, PublicationOperationEventRow("resumed", lease.operation_id,
                        "recover", event.event_seq + 2, "ready", 2))
                self.assertEqual(await holders.holders(ref), (OperationHolder(lease=lease),))
                with self.assertRaises(ValueError):
                    await holders.acquire(ref, OperationHolder(lease=lease))
        run_async(check())
