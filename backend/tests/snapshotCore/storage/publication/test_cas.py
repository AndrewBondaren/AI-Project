"""Schema-level publication/lineage gates; adapters and CAS races belong to 4C2."""

import sqlite3
import unittest
from app.db.mapper import model_columns
from tests.snapshotCore.support.fixtures import (
    CORE_MODELS, new_database, validate_models, insert, operation, outcome, bootstrap, started, tick, snapshot_values,
)


class PublicationCasTests(unittest.TestCase):
    def setUp(self):
        self.conn = new_database()
        self.addCleanup(self.conn.close)

    def test_existing_schema_validator_and_exact_row_columns(self):
        validate_models(self.conn)
        for model in CORE_MODELS:
            with self.subTest(model=model.__name__):
                columns = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({model.__table__})")}
                self.assertEqual(columns, model_columns(model))
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_foreign_keys_reject_missing_world_identity(self):
        with self.assertRaisesRegex(sqlite3.IntegrityError, "FOREIGN KEY"):
            insert(self.conn, "publication_operations", operation_id="orphan", world_uid="missing",
                   kind="snapshot_apply", preparation_fingerprint="a" * 64)

    def test_bootstrap_has_one_empty_root_and_no_fake_snapshot(self):
        root = bootstrap(self.conn)
        self.assertIsNone(root["snapshot_head_id"])
        for changes in ({"publication_id": "another"}, {"publication_id": "bad", "gameplay_started": 1},
                        {"publication_id": "bad", "pack_hash": "a" * 64}):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "world_publications", **{**root, **changes})
        self.assertEqual(self.conn.execute("SELECT count(*) FROM world_snapshots").fetchone()[0], 0)

    def test_one_operation_cannot_append_two_publications_even_before_terminal(self):
        bootstrap(self.conn)
        operation(self.conn, "activate", kind="pack_activation")
        active = dict(publication_id="active", world_uid="w1", predecessor_id="root", publication_seq=2,
                      operation_id="activate", pack_hash="d" * 64, snapshot_head_id=None,
                      active_timeline_id=None, gameplay_started=0)
        insert(self.conn, "world_publications", **active)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "world_publications", **{**active, "publication_id": "duplicate",
                   "predecessor_id": "active", "publication_seq": 3})

    def test_pregame_start_tick_and_player_heads_are_distinct_chains(self):
        started(self.conn)
        first = tick(self.conn, "tick1", ("p1", "p3"))
        second = tick(self.conn, "tick2", ("p1",))
        self.assertEqual(second["parent_snapshot_id"], first["snapshot_id"])
        self.assertEqual(second["turn_id"], 2)
        heads = dict(self.conn.execute("SELECT player_uid, max(publication_seq) FROM player_publications GROUP BY player_uid"))
        self.assertEqual(heads, {"p1": 2, "p3": 1})
        self.assertEqual(self.conn.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_publication_rejects_forks_wrong_sequence_wrong_world_and_gameplay_reversal(self):
        base = started(self.conn)
        operation(self.conn, "next")
        for changes in (
            {"publication_seq": 5}, {"world_uid": "w2"}, {"gameplay_started": 0},
            {"pack_hash": "e" * 64}, {"active_timeline_id": "t2"}, {"snapshot_head_id": None},
            {"predecessor_id": "active", "publication_seq": 3},
        ):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "world_publications", **{**base, "publication_id": "bad", "predecessor_id": "started",
                    "publication_seq": 4, "operation_id": "next", **changes})

    def test_snapshot_and_player_owner_parent_tick_and_audit_guards(self):
        started(self.conn)
        operation(self.conn, "next")
        world = snapshot_values(self.conn, "next")
        for changes in ({"turn_id": 0}, {"turn_id": 1.5}, {"timeline_id": "t2"}, {"world_uid": "w2"},
                        {"parent_snapshot_id": "missing"}, {"base_pack_hash": "c" * 64},
                        {"snapshot_checksum": "bad"}, {"snapshot_data": "text"}):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "world_snapshots", **{**world, **changes})
        insert(self.conn, "world_snapshots", **world)
        player = dict(player_snapshot_id="ps", player_uid="p1", world_uid="w1", timeline_id="t1", session_id=None,
                      turn_id=1, created_at=world["created_at"], parent_player_snapshot_id=None, operation_id="next",
                      envelope_format_version=1, snapshot_data=b"player", snapshot_checksum="e" * 64)
        for changes in ({"player_uid": "p2"}, {"session_id": "s2"}, {"parent_player_snapshot_id": "missing"},
                        {"turn_id": 2}, {"timeline_id": "t2"}):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "player_snapshots", **{**player, **changes})
        insert(self.conn, "player_snapshots", **{**player, "session_id": "s1"})

    def test_operation_bindings_phases_fences_and_terminal_category_guards(self):
        operation(self.conn, "op")
        for phase, fence in (("preparing", 1), ("applying", 1), ("ready", 1), ("recovery_required", 2), ("terminal", 1)):
            with self.subTest(phase=phase), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "publication_operation_events", event_id="bad", operation_id="op",
                       predecessor_id="op-event", event_seq=2, phase=phase, fence=fence)
        outcome(self.conn, "op", "snapshot_apply", "conflict")
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "publication_operation_events", event_id="after", operation_id="op",
                   predecessor_id="op-terminal", event_seq=3, phase="ready", fence=2)
        for kind in ("pack_activation", "gameplay_start"):
            operation(self.conn, kind, kind=kind)
            outcome(self.conn, kind, "snapshot_apply", "rejected")
        operation(self.conn, "cancel", phase="preparing", bound=False)
        outcome(self.conn, "cancel", "cancelled")

    def test_success_refusal_and_cancellation_cannot_hide_published_state(self):
        started(self.conn)
        operation(self.conn, "next")
        values = dict(operation_id="next", outcome_kind="snapshot_apply", category="committed",
                      format_version=1, outcome_data=b"outcome", outcome_checksum="c" * 64)
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "publication_outcomes", **values)
        insert(self.conn, "world_snapshots", **snapshot_values(self.conn, "next"))
        for changes in ({"category": "rejected"}, {"category": None, "outcome_kind": "cancelled"},
                        {"category": None, "outcome_kind": "gameplay_start"}):
            with self.subTest(changes=changes), self.assertRaises(sqlite3.IntegrityError):
                insert(self.conn, "publication_outcomes", **{**values, **changes})

    def test_success_cannot_finish_preparation_without_claim_and_request(self):
        operation(self.conn, "not-claimed", kind="pack_activation", phase="preparing")
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "publication_outcomes", operation_id="not-claimed", outcome_kind="pack_activation",
                   category=None, format_version=1, outcome_data=b"not a publication", outcome_checksum="c" * 64)

    def test_current_state_indices_support_direct_owner_lookup(self):
        for table, owner, sequence in (("world_publications", "world_uid", "publication_seq"),
            ("player_publications", "player_uid", "publication_seq"),
            ("publication_operation_events", "operation_id", "event_seq"),
            ("artifact_storage_events", "artifact_id", "event_seq"),
            ("artifact_lease_events", "operation_id", "event_seq")):
            plan = self.conn.execute(f"EXPLAIN QUERY PLAN SELECT * FROM {table} WHERE {owner}=? ORDER BY {sequence} DESC LIMIT 1", ("owner",)).fetchall()
            self.assertTrue(any("INDEX" in row["detail"] for row in plan), (table, plan))
            self.assertFalse(any("TEMP B-TREE" in row["detail"] for row in plan), (table, plan))
