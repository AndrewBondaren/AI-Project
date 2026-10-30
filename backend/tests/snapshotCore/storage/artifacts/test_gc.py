"""DDL live-set/representation gates; no physical deletion or scheduler."""

import sqlite3
import unittest
from tests.snapshotCore.support.fixtures import new_database, stage, close_writers, insert, started, tick


class ArtifactGcTests(unittest.TestCase):
    def setUp(self):
        self.conn = new_database()
        self.addCleanup(self.conn.close)

    def test_gc_refuses_live_holds_and_writers_and_accepts_unheld_sealed_content(self):
        descriptor, hold, claim, storage = stage(self.conn)
        deleted = dict(event_id="deleted", artifact_id="artifact", predecessor_id=storage["event_id"], event_seq=2, kind="gc_deleted")
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_storage_events", **deleted)
        close_writers(self.conn)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_storage_events", **deleted)
        insert(self.conn, "artifact_holder_events", **{**hold, "event_id": "release", "predecessor_id": hold["event_id"], "event_seq": 2, "event_kind": "release"})
        insert(self.conn, "artifact_storage_events", **deleted)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_storage_events", **{**deleted, "event_id": "duplicate", "predecessor_id": "deleted", "event_seq": 3})

    def test_snapshot_hold_is_typed_permanent_and_blocks_gc_after_operation_release(self):
        descriptor, hold, claim, storage = stage(self.conn)
        started(self.conn)
        world = tick(self.conn, players=("p1",))
        published = {**hold, "event_id": "published", "holder_kind": "snapshot", "operation_id": None,
                     "fence": None, "world_snapshot_id": world["snapshot_id"]}
        insert(self.conn, "artifact_holder_events", **published)
        for changes in ({"player_snapshot_id": "tick-p1"}, {"operation_id": "stage"}, {"world_snapshot_id": "missing"}):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "artifact_holder_events", **{**published, "event_id": "bad", **changes})
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_holder_events", **{**published, "event_id": "release-history",
                   "predecessor_id": "published", "event_seq": 2, "event_kind": "release"})
        close_writers(self.conn)
        insert(self.conn, "artifact_holder_events", **{**hold, "event_id": "release-operation", "predecessor_id": hold["event_id"], "event_seq": 2, "event_kind": "release"})
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "artifact_storage_events", event_id="gc", artifact_id="artifact",
                   predecessor_id=storage["event_id"], event_seq=2, kind="gc_deleted")

    def test_catalog_checks_and_unique_identity_cannot_be_overwritten_by_replace(self):
        descriptor, *_ = stage(self.conn)
        for changes in ({"kind": "unknown"}, {"nbytes": -1}, {"nbytes": 0.5}, {"format_version": 0},
                        {"row_count": 0}, {"kind": "sql_rows"}, {"content_hash": "bad"}):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "artifact_catalog", **{**descriptor, "artifact_id": "bad", **changes})
        values = {**descriptor, "artifact_id": "different-id", "nbytes": 200}
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(f"INSERT OR REPLACE INTO artifact_catalog ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
        insert(self.conn, "artifact_catalog", **{**descriptor, "artifact_id": "rows", "kind": "sql_rows", "row_count": 0})

    def test_retention_holder_requires_an_existing_artifact_owner(self):
        descriptor, hold, claim, storage = stage(self.conn)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "FOREIGN KEY"):
            insert(self.conn, "artifact_holder_events", **{**hold, "event_id": "retention", "holder_kind": "artifact",
                   "operation_id": None, "fence": None, "retained_artifact_id": "missing"})
