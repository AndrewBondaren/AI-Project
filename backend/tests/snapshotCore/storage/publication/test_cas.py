"""Schema-level publication/lineage gates; adapters and CAS races belong to 4C2."""

import sqlite3
import unittest
import asyncio
from unittest.mock import patch, AsyncMock
from pydantic import ValidationError
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase
from app.dataModel.artifacts.lifecycle.operation.claim import PublicationBusy, PublicationTerminal
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.publication import CasDecision, PackActivationResult, PackActivationDisposition
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.artifacts.references import ArtifactRef, ArtifactKind, ArtifactFormatRegistry
from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.db.mapper import model_columns
from tests.snapshotCore.support.fixtures import (
    CORE_MODELS, new_database, validate_models, insert, operation, outcome, bootstrap, started, tick, snapshot_values,
    run_async, live_database, live_started, live_tick, unsafe_update,
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

    def test_adapter_terminal_retry_busy_and_immutable_world_binding(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                claim, result = await live_tick(bundle, "first")
                await live_tick(bundle, "second")
                operations = bundle[-1]
                with patch.object(bundle[2], "read", side_effect=AssertionError("must not read current targets")):
                    retry = await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "first", "w1", "a" * 64, "b" * 64)
                self.assertIsInstance(retry, PublicationTerminal)
                self.assertEqual(retry.record.terminal, result)
                for kind, world, prep, request in (
                    (OperationKind.PACK_ACTIVATION, "w1", "a" * 64, "b" * 64),
                    (OperationKind.SNAPSHOT_APPLY, "w2", "a" * 64, "b" * 64),
                    (OperationKind.SNAPSHOT_APPLY, "w1", "c" * 64, "b" * 64),
                    (OperationKind.SNAPSHOT_APPLY, "w1", "a" * 64, "c" * 64),
                ):
                    with self.assertRaises(ValueError):
                        await operations.claim_publication(kind, "first", world, prep, request)
                await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "busy", "w1", "a" * 64, "b" * 64)
                busy = await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "busy", "w1", "a" * 64, "b" * 64)
                self.assertIsInstance(busy, PublicationBusy)
                self.assertEqual((await operations.read("first")).terminal, result)
        run_async(check())

    def test_adapter_two_connection_cas_has_one_winner_and_durable_refusal(self):
        async def check():
            async with live_database() as first:
                async with first[1].transaction("bootstrap") as scope:
                    await first[2].initialize(scope, "w1")
                async with live_database(first[0].path, seed=False) as second:
                    barrier = asyncio.Barrier(2)
                    async def race(bundle, name, digest):
                        db, commits, world, players, history, operations = bundle
                        expected = await world.read("w1")
                        claim = await operations.claim_publication(OperationKind.PACK_ACTIVATION, name, "w1", "a" * 64, "b" * 64)
                        await barrier.wait()
                        publication = WorldPublicationRef(world_uid="w1", publication_id=name + "-pub", pack_hash=digest,
                            snapshot_head=None, active_timeline_id=None, gameplay_started=False)
                        async with commits.transaction(name) as scope:
                            decision = await world.compare_append(scope, expected, publication)
                            if decision is CasDecision.APPLIED:
                                artifact = ArtifactRef(kind=ArtifactKind.BLOB, format_key=RegistryKey[ArtifactFormatRegistry]("test.manifest"),
                                                       format_version=1, content_hash=digest, nbytes=0)
                                await operations.record_terminal(scope, PackActivationResult(operation_id=name,
                                    request_fingerprint="b" * 64, manifest=artifact, disposition=PackActivationDisposition.ACTIVE,
                                    publication=publication))
                        if decision is CasDecision.MISMATCH:
                            await operations.record_refusal(claim, SnapshotApplyResult(category=SnapshotApplyOutcomeKind.CONFLICT,
                                operation_id=name, request_fingerprint="b" * 64, committed=None,
                                diagnostics=(FieldPathError(path=(), message="stale publication"),)))
                        return decision
                    decisions = await asyncio.gather(race(first, "race1", "c" * 64), race(second, "race2", "d" * 64))
                    self.assertEqual(decisions.count(CasDecision.APPLIED), 1)
                    self.assertEqual(decisions.count(CasDecision.MISMATCH), 1)
                    for name in ("race1", "race2"):
                        self.assertIs((await first[-1].read(name)).phase, OperationPhase.TERMINAL)
        run_async(check())

    def test_adapter_rejects_invalid_inputs_before_claim_or_publication_writes(self):
        async def check():
            async with live_database() as bundle:
                db, commits, world, players, history, operations = bundle
                for uid in ("", " bad ", None, 123):
                    with self.assertRaises((ValueError, TypeError)):
                        await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, uid, "w1", "a" * 64, "b" * 64)
                    with self.assertRaises((ValueError, TypeError)):
                        await world.read(uid)
                    with self.assertRaises((ValueError, TypeError)):
                        await players.read(uid)
                with self.assertRaises(ValidationError):
                    await operations.claim_publication("snapshot_apply", "op", "w1", "a" * 64, "b" * 64)
                with patch("app.db.repositories.sqlite.snapshotCore.operations.operationStore.runtime_uid", return_value=" "):
                    with patch.object(operations._access, "insert", new_callable=AsyncMock) as write:
                        with self.assertRaises(ValidationError):
                            await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "op", "w1", "a" * 64, "b" * 64)
                        write.assert_not_called()
                async with db.conn.execute("SELECT count(*) FROM publication_operations") as cursor:
                    self.assertEqual((await cursor.fetchone())[0], 0)
        run_async(check())

    def test_adapter_read_validates_internal_ids_tags_flags_and_checksums(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                await live_tick(bundle)
                db, commits, world, players, history, operations = bundle
                async with db.conn.execute("SELECT event_id FROM publication_operation_events WHERE operation_id='tick' ORDER BY event_seq DESC LIMIT 1") as cursor:
                    event_id = (await cursor.fetchone())[0]
                cases = (
                    ("publication_operation_events", "event_id", event_id, "event_id", " "),
                    ("publication_operation_events", "event_id", event_id, "predecessor_id", " bad "),
                    ("publication_operation_events", "event_id", event_id, "event_seq", 0),
                    ("publication_operation_events", "event_id", event_id, "fence", 0),
                    ("publication_operation_events", "event_id", event_id, "phase", "unknown"),
                    ("publication_operations", "operation_id", "tick", "world_uid", " w1 "),
                    ("publication_operations", "operation_id", "tick", "kind", "unknown"),
                    ("publication_operations", "operation_id", "tick", "preparation_fingerprint", "bad"),
                    ("publication_requests", "operation_id", "tick", "publication_fingerprint", "bad"),
                    ("publication_outcomes", "operation_id", "tick", "outcome_kind", "unknown"),
                    ("publication_outcomes", "operation_id", "tick", "category", "unknown"),
                    ("publication_outcomes", "operation_id", "tick", "format_version", 2),
                    ("publication_outcomes", "operation_id", "tick", "outcome_data", b"corrupt"),
                    ("publication_outcomes", "operation_id", "tick", "outcome_checksum", "f" * 64),
                    ("world_publications", "publication_id", "tick-pub", "gameplay_started", 2),
                    ("world_publications", "publication_id", "tick-pub", "publication_seq", 0),
                    ("player_publications", "player_snapshot_id", "tick-player", "player_uid", " bad "),
                    ("player_publications", "player_snapshot_id", "tick-player", "publication_seq", 0),
                )
                for table, key, identity, column, value in cases:
                    with self.subTest(table=table, column=column):
                        previous = await unsafe_update(db, table, key, identity, column, value)
                        try:
                            with self.assertRaises((ValueError, PublicationInfrastructureError)):
                                await operations.read("tick")
                        finally:
                            lookup = value if column == key else identity
                            await unsafe_update(db, table, key, lookup, column, previous)
        run_async(check())

    def test_adapter_preparing_is_busy_and_ready_claim_binds_request_once(self):
        async def check():
            async with live_database() as bundle:
                db, commits, world, players, history, operations = bundle
                async with db.transaction():
                    await db.conn.execute("INSERT INTO publication_operations VALUES ('prepared','w1','snapshot_apply',?)", ("a" * 64,))
                    await db.conn.execute("INSERT INTO publication_operation_events VALUES ('preparing','prepared',NULL,1,'preparing',1)")
                result = await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "prepared", "w1", "a" * 64, "b" * 64)
                self.assertIsInstance(result, PublicationBusy)
                self.assertIsNone((await operations.read("prepared")).publication_fingerprint)
                async with db.transaction():
                    await db.conn.execute("INSERT INTO publication_operation_events VALUES ('ready','prepared','preparing',2,'ready',1)")
                owner = await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "prepared", "w1", "a" * 64, "b" * 64)
                self.assertEqual(owner.lease.fence, 1)
                self.assertEqual((await operations.read("prepared")).publication_fingerprint, "b" * 64)
                bad = owner.model_copy(update={"lease": owner.lease.model_copy(update={"fence": 2})})
                refusal = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.REJECTED, operation_id="prepared",
                    request_fingerprint="b" * 64, committed=None, diagnostics=(FieldPathError(path=(), message="stale"),))
                with self.assertRaises(ValueError):
                    await operations.record_refusal(bad, refusal)
                self.assertIsNone((await operations.read("prepared")).terminal)
        run_async(check())

    def test_adapter_history_columns_are_validated_and_match_the_canonical_envelope(self):
        from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef, PlayerSnapshotRef
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                await live_tick(bundle)
                db, commits, world, players, history, operations = bundle
                cases = (
                    ("world_snapshots", "snapshot_id", "tick-world", "timeline_id", " other "),
                    ("world_snapshots", "snapshot_id", "tick-world", "world_uid", " other "),
                    ("world_snapshots", "snapshot_id", "tick-world", "operation_id", " bad "),
                    ("world_snapshots", "snapshot_id", "tick-world", "parent_snapshot_id", "missing"),
                    ("world_snapshots", "snapshot_id", "tick-world", "turn_id", 0),
                    ("world_snapshots", "snapshot_id", "tick-world", "turn_id", 1.5),
                    ("world_snapshots", "snapshot_id", "tick-world", "created_at", "2026-10-30T00:00:01.000000Z"),
                    ("world_snapshots", "snapshot_id", "tick-world", "created_at", "not UTC"),
                    ("world_snapshots", "snapshot_id", "tick-world", "envelope_format_version", 2),
                    ("world_snapshots", "snapshot_id", "tick-world", "base_pack_hash", "c" * 64),
                    ("world_snapshots", "snapshot_id", "tick-world", "snapshot_data", b"corrupt"),
                    ("world_snapshots", "snapshot_id", "tick-world", "snapshot_checksum", "f" * 64),
                    ("player_snapshots", "player_snapshot_id", "tick-player", "player_uid", "different-player"),
                    ("player_snapshots", "player_snapshot_id", "tick-player", "world_uid", "different-world"),
                    ("player_snapshots", "player_snapshot_id", "tick-player", "timeline_id", "different-timeline"),
                    ("player_snapshots", "player_snapshot_id", "tick-player", "session_id", "missing"),
                    ("player_snapshots", "player_snapshot_id", "tick-player", "parent_player_snapshot_id", "missing"),
                )
                for table, key, identity, column, value in cases:
                    ref = (WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="tick-world") if table == "world_snapshots"
                           else PlayerSnapshotRef(player_uid="p1", snapshot_id="tick-player"))
                    with self.subTest(table=table, column=column):
                        previous = await unsafe_update(db, table, key, identity, column, value)
                        try:
                            with self.assertRaises((ValueError, PublicationInfrastructureError)):
                                await history.read(ref)
                        finally:
                            await unsafe_update(db, table, key, identity, column, previous)
        run_async(check())

    def test_adapter_revalidates_constructed_metadata_before_any_insert(self):
        from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
        from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata
        from tests.snapshotCore.support.fixtures import STAMP
        async def check():
            async with live_database() as bundle:
                metadata = WorldSnapshotMetadata(ref=WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="new"),
                    parent=None, operation_id="validate", turn_id=1, created_at=STAMP, envelope_format_version=1,
                    base_pack_hash="d" * 64, state_refs=(), history_refs=(), retained_artifacts=())
                invalid = (
                    metadata.model_copy(update={"turn_id": True}), metadata.model_copy(update={"turn_id": "1"}),
                    metadata.model_copy(update={"turn_id": 1.5}), metadata.model_copy(update={"base_pack_hash": "bad"}),
                    metadata.model_copy(update={"operation_id": " validate "}), metadata.model_copy(update={"created_at": "today"}),
                    metadata.model_copy(update={"ref": metadata.ref.model_copy(update={"snapshot_id": ""})}),
                    metadata.model_copy(update={"envelope_format_version": 2}), metadata.model_copy(update={"state_refs": []}),
                )
                async with bundle[1].transaction("validate") as scope:
                    with patch.object(bundle[4]._access, "insert", new_callable=AsyncMock) as write:
                        for value in invalid:
                            with self.assertRaises((ValueError, TypeError)):
                                await bundle[4].append(scope, value, ())
                        write.assert_not_called()
        run_async(check())
