"""DDL lease/writer/fence invariants; actual shared guards belong to 4C3."""

import sqlite3
import unittest
from tests.snapshotCore.support.fixtures import new_database, stage, close_writers, insert, operation


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
