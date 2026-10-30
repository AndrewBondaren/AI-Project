"""Append-only schema and rollback probes, not a production transaction adapter."""

import sqlite3
import unittest
from app.db.mapper import from_row, to_row
from tests.snapshotCore.support.fixtures import (
    CORE_MODELS, new_database, started, tick, stage, operation, insert, snapshot_values,
)


class AtomicSnapshotCommitTests(unittest.TestCase):
    def setUp(self):
        self.conn = new_database()
        self.addCleanup(self.conn.close)

    def test_every_core_table_forbids_update_delete_and_replace_with_recursive_triggers_off(self):
        started(self.conn)
        tick(self.conn, players=("p1",))
        stage(self.conn)
        self.assertEqual(self.conn.execute("PRAGMA recursive_triggers").fetchone()[0], 0)
        for model in CORE_MODELS:
            table, key = model.__table__, model.__pk__
            row = self.conn.execute(f"SELECT * FROM {table} LIMIT 1").fetchone()
            self.assertIsNotNone(row, table)
            values = dict(row)
            for statement, args in (
                (f"UPDATE {table} SET {key}={key} WHERE {key}=?", (row[key],)),
                (f"DELETE FROM {table} WHERE {key}=?", (row[key],)),
                (f"INSERT OR REPLACE INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values())),
            ):
                with self.subTest(table=table, statement=statement), self.assertRaises(sqlite3.IntegrityError):
                    self.conn.execute(statement, args)
            self.assertEqual(dict(self.conn.execute(f"SELECT * FROM {table} WHERE {key}=?", (row[key],)).fetchone()), values)

    def test_mapper_roundtrip_and_frozen_rows_cover_every_table(self):
        started(self.conn)
        tick(self.conn, players=("p1",))
        stage(self.conn)
        for model in CORE_MODELS:
            row = self.conn.execute(f"SELECT * FROM {model.__table__} LIMIT 1").fetchone()
            mapped = from_row(model, row)
            names, values = to_row(mapped)
            self.assertEqual(dict(zip(names, values)), dict(row))

    def test_schema_failure_rolls_back_prepared_snapshot_rows_without_advancing_heads(self):
        started(self.conn)
        self.conn.execute("SAVEPOINT snapshot_attempt")
        operation(self.conn, "failed")
        insert(self.conn, "world_snapshots", **snapshot_values(self.conn, "failed"))
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.conn, "player_publications", publication_id="bad", player_uid="p1", predecessor_id=None,
                   publication_seq=1, player_snapshot_id="missing", operation_id="failed")
        self.conn.execute("ROLLBACK TO snapshot_attempt")
        self.conn.execute("RELEASE snapshot_attempt")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM world_snapshots").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM publication_operations WHERE operation_id='failed'").fetchone()[0], 0)
        self.assertEqual(self.conn.execute("SELECT snapshot_head_id FROM world_publications ORDER BY publication_seq DESC LIMIT 1").fetchone()[0], None)
