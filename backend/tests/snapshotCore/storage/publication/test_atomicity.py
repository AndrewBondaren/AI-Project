"""Append-only schema and rollback probes, not a production transaction adapter."""

import sqlite3
import unittest
import asyncio
import threading
from contextlib import closing
from unittest.mock import patch
from app.application.publication.errors import UnknownCommitOutcome
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationPhase, OperationKind
from app.dataModel.artifacts.lifecycle.operation.claim import PublicationTerminal
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.db.mapper import from_row, to_row
from tests.snapshotCore.support.fixtures import (
    CORE_MODELS, new_database, started, tick, stage, operation, insert, snapshot_values,
    run_async, live_database, live_started, live_tick, close_writers,
)


class AtomicSnapshotCommitTests(unittest.TestCase):
    def test_terminal_codec_and_historical_evidence_boundaries(self):
        from dataclasses import replace
        from app.application.publication.errors import PublicationInfrastructureError
        from app.db.repositories.sqlite.snapshotCore.operations.terminalCodec import StoredTerminalCodec

        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                _, result = await live_tick(bundle)
                codec = StoredTerminalCodec()
                row = codec.encode(result)
                self.assertEqual(codec.decode(row), result)
                for changes in ({"outcome_checksum": "0" * 64}, {"outcome_kind": "unknown"},
                                {"format_version": 2}, {"operation_id": "other"},
                                {"category": "conflict"}):
                    with self.subTest(changes=changes), self.assertRaises((PublicationInfrastructureError, ValueError)):
                        codec.decode(replace(row, **changes))
                # A newer head must not invalidate the earlier terminal's historical refs.
                await live_tick(bundle, "next")
                async with bundle[1].read_scope() as scope:
                    await bundle[-1]._evidence.check(scope, result)
                    forged = result.model_copy(update={"operation_id": "missing"})
                    with self.assertRaises(PublicationInfrastructureError):
                        await bundle[-1]._evidence.check(scope, forged)
                self.assertEqual((await bundle[-1].read("tick")).terminal, result)
        run_async(check())

    def test_typed_row_boundary_shape_values_and_scope(self):
        from app.application.publication.errors import PublicationInfrastructureError
        from app.db.models.snapshotCore.operationRows import PublicationOperationRow
        from app.db.repositories.sqlite.shared.validation.rowValues import _values

        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                access = bundle[2]._access
                sql = "SELECT * FROM publication_operations ORDER BY operation_id"
                async with bundle[1].read_scope() as scope:
                    rows = await access.all_rows(scope, PublicationOperationRow, sql)
                    self.assertTrue(rows)
                    self.assertTrue(all(isinstance(row, PublicationOperationRow) for row in rows))
                    self.assertEqual(await access.one_row(scope, PublicationOperationRow, sql), rows[0])
                    self.assertIsNone(await access.one_row(scope, PublicationOperationRow, sql + " LIMIT 0"))
                    self.assertEqual(await access.all_rows(scope, PublicationOperationRow, sql + " LIMIT 0"), [])
                    for read in (access.one_row, access.all_rows):
                        with self.assertRaises(PublicationInfrastructureError):
                            await read(scope, PublicationOperationRow, "SELECT operation_id FROM publication_operations")
                    # Mapping must preserve invalid scalars for strict boundary validation.
                    corrupt = await access.one_row(scope, PublicationOperationRow,
                        "SELECT 5 AS operation_id, world_uid, kind, preparation_fingerprint FROM publication_operations LIMIT 1")
                    self.assertIsNotNone(corrupt)
                    with self.assertRaises(PublicationInfrastructureError):
                        _values(uids=(corrupt.operation_id,))
                    async with live_database(bundle[0].path, seed=False) as other:
                        with self.assertRaises(PublicationInfrastructureError):
                            await other[2]._access.one_row(scope, PublicationOperationRow, sql)
                for read in (access.one_row, access.all_rows):
                    with self.assertRaises(PublicationInfrastructureError):
                        await read(scope, PublicationOperationRow, sql)
        run_async(check())

    def test_artifact_read_leaf_active_release_and_scope_guards(self):
        from app.application.publication.errors import PublicationInfrastructureError
        from app.db.repositories.sqlite.artifacts.operationArtifacts import SqliteOperationArtifacts

        async def check():
            async with live_database() as bundle:
                with closing(sqlite3.connect(bundle[0].path)) as conn, conn:
                    _, hold, _, _ = stage(conn)
                    close_writers(conn)
                leaf = SqliteOperationArtifacts(bundle[2]._access)
                async with bundle[1].read_scope() as scope:
                    refs = await leaf.read(scope, "stage")
                    self.assertEqual(len(refs), 1)
                    async with live_database(bundle[0].path, seed=False) as other:
                        with self.assertRaises(PublicationInfrastructureError):
                            await other[-1]._artifacts.read(scope, "stage")
                with self.assertRaises(PublicationInfrastructureError):
                    await leaf.read(scope, "stage")
                self.assertEqual(refs, (await bundle[-1].read("stage")).leased_artifacts)
                with closing(sqlite3.connect(bundle[0].path)) as conn, conn:
                    insert(conn, "artifact_holder_events", **{**hold, "event_id": "released",
                           "predecessor_id": hold["event_id"], "event_seq": 2, "event_kind": "release"})
                async with bundle[1].read_scope() as scope:
                    self.assertEqual(await leaf.read(scope, "stage"), ())
        run_async(check())

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

    def test_adapter_world_player_history_and_outcome_commit_or_rollback_as_one(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                claims = []
                with self.assertRaises(RuntimeError):
                    await live_tick(bundle, "failed", fail=True, claims=claims)
                self.assertEqual(await bundle[2].read("w1"), expected)
                self.assertIsNone(await bundle[3].read("p1"))
                async with bundle[0].conn.execute("SELECT count(*) FROM world_snapshots") as cursor:
                    self.assertEqual((await cursor.fetchone())[0], 0)
                refusal = SnapshotApplyResult(category=SnapshotApplyOutcomeKind.CONFLICT, operation_id="failed",
                    request_fingerprint="b" * 64, committed=None, diagnostics=(FieldPathError(path=(), message="conflict"),))
                await bundle[-1].record_refusal(claims[0], refusal)
                self.assertEqual((await bundle[-1].read("failed")).terminal, refusal)
                claim, success = await live_tick(bundle)
                self.assertEqual((await bundle[-1].read("tick")).terminal, success)
                self.assertEqual((await bundle[2].read("w1")).snapshot_head, success.committed.world_snapshot)
                self.assertEqual(await bundle[3].read("p1"), success.committed.player_snapshots[0])
        run_async(check())

    def test_adapter_lost_commit_ack_quarantines_connection_and_recovers_terminal(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                db, commits, world, players, history, operations = bundle
                original = commits.driver.commit
                reached_commit, release_commit = asyncio.Event(), asyncio.Event()
                async def lose_ack(conn):
                    async with conn.execute("SELECT count(*) FROM world_snapshots WHERE operation_id='tick'") as cursor:
                        publication = bool((await cursor.fetchone())[0])
                    if publication:
                        reached_commit.set()
                        await release_commit.wait()
                    cancelled = await original(conn)
                    if publication:
                        raise OSError("lost COMMIT acknowledgement")
                    return cancelled
                claims = []
                with patch.object(commits.driver, "commit", lose_ack):
                    pending = asyncio.create_task(live_tick(bundle, claims=claims))
                    await reached_commit.wait()
                    queued = asyncio.create_task(operations.read("tick"))
                    await asyncio.sleep(0.02)
                    self.assertFalse(queued.done())
                    release_commit.set()
                    with self.assertRaises(UnknownCommitOutcome):
                        await pending
                    with self.assertRaises(UnknownCommitOutcome):
                        await queued
                with self.assertRaises(UnknownCommitOutcome):
                    await operations.read("tick")
                with self.assertRaises(UnknownCommitOutcome):
                    await operations.record_refusal(claims[0], SnapshotApplyResult(category=SnapshotApplyOutcomeKind.REJECTED,
                        operation_id="tick", request_fingerprint="b" * 64, committed=None,
                        diagnostics=(FieldPathError(path=(), message="must not replace unknown outcome"),)))
                async with live_database(db.path, seed=False) as recovery:
                    result = (await recovery[-1].read("tick")).terminal
                    self.assertIs(result.category, SnapshotApplyOutcomeKind.COMMITTED)
                    with patch.object(recovery[2], "read", side_effect=AssertionError("retry must not read current targets")):
                        retry = await recovery[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, "tick", "w1", "a" * 64, "b" * 64)
                    self.assertIsInstance(retry, PublicationTerminal)
                    self.assertEqual(retry.record.terminal, result)
        run_async(check())

    def test_lost_rollback_ack_and_failed_close_keep_registry_quarantined(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                db, commits, world, players, history, operations = bundle
                rollback = commits.driver.rollback
                async def lose_ack(conn):
                    async with conn.execute("SELECT count(*) FROM world_snapshots WHERE operation_id='tick'") as cursor:
                        publication = bool((await cursor.fetchone())[0])
                    cancelled = await rollback(conn)
                    if publication:
                        raise OSError("lost ROLLBACK acknowledgement")
                    return cancelled
                async def failed_close(conn):
                    raise OSError("driver close failed")
                with patch.object(commits.driver, "rollback", lose_ack), patch.object(commits.driver, "close", failed_close):
                    with self.assertRaises(UnknownCommitOutcome):
                        await live_tick(bundle, fail=True)
                with self.assertRaises(UnknownCommitOutcome):
                    await operations.read("tick")
                with self.assertRaises(UnknownCommitOutcome):
                    async with commits.transaction("retry"):
                        self.fail("quarantined connection must not issue a scope")
                async with live_database(db.path, seed=False) as recovery:
                    self.assertEqual(await recovery[2].read("w1"), expected)
                    self.assertIsNone((await recovery[-1].read("tick")).terminal)
        run_async(check())

    def test_adapter_body_cancellation_rolls_back_without_fabricating_a_terminal(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                entered, hold = asyncio.Event(), asyncio.Event()
                pending = asyncio.create_task(live_tick(bundle, entered=entered, hold=hold))
                await entered.wait()
                pending.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await pending
                self.assertEqual(await bundle[2].read("w1"), expected)
                self.assertIsNone(await bundle[3].read("p1"))
                record = await bundle[-1].read("tick")
                self.assertIs(record.phase, OperationPhase.APPLYING)
                self.assertIsNone(record.terminal)
        run_async(check())

    def test_adapter_commit_cancellation_drains_worker_before_releasing_gate(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                entered = asyncio.Event()
                worker_started, release = threading.Event(), threading.Event()
                def trace(sql):
                    if sql == "COMMIT" and entered.is_set():
                        worker_started.set()
                        if not release.wait(5):
                            raise AssertionError("test failed to release COMMIT worker")
                await bundle[0].conn.set_trace_callback(trace)
                pending = asyncio.create_task(live_tick(bundle, entered=entered))
                try:
                    self.assertTrue(await asyncio.to_thread(worker_started.wait, 4))
                    pending.cancel()
                    observer = asyncio.create_task(bundle[2].read("w1"))
                    await asyncio.sleep(0.02)
                    self.assertFalse(pending.done())
                    self.assertFalse(observer.done())
                    release.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await pending
                    self.assertIsNotNone((await observer).snapshot_head)
                    result = (await bundle[-1].read("tick")).terminal
                    self.assertIs(result.category, SnapshotApplyOutcomeKind.COMMITTED)
                finally:
                    release.set()
                    await bundle[0].conn.set_trace_callback(None)
                    if not pending.done():
                        await pending
        run_async(check())

    def test_adapter_cancellation_while_rolling_back_does_not_become_the_original_error(self):
        async def check():
            async with live_database() as bundle:
                expected = await live_started(bundle)
                publication_written, worker_started, release = threading.Event(), threading.Event(), threading.Event()
                def trace(sql):
                    if sql.startswith("INSERT INTO world_publications") and "tick-pub" in sql:
                        publication_written.set()
                    if sql == "ROLLBACK" and publication_written.is_set():
                        worker_started.set()
                        release.wait(5)
                await bundle[0].conn.set_trace_callback(trace)
                pending = asyncio.create_task(live_tick(bundle, fail=True))
                try:
                    self.assertTrue(await asyncio.to_thread(worker_started.wait, 4))
                    pending.cancel()
                    await asyncio.sleep(0.02)
                    self.assertFalse(pending.done())
                    release.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await pending
                    await bundle[0].conn.set_trace_callback(None)
                    self.assertEqual(await bundle[2].read("w1"), expected)
                    self.assertIsNone((await bundle[-1].read("tick")).terminal)
                finally:
                    release.set()
                    await bundle[0].conn.set_trace_callback(None)
                    if not pending.done():
                        await pending
        run_async(check())


class AssignedPublicationTests(unittest.TestCase):
    def test_handlers_and_sqlite_cas_share_target_and_rollback(self):
        from unittest.mock import Mock, AsyncMock
        from app.application.publication.errors import PublicationInfrastructureError
        from app.db.models.snapshotCore.operationRows import PublicationOperationRow
        from app.application.patch.registry.sectionRegistry import SectionRegistry, BoundSectionHandler
        from app.application.worldSnapshot.contracts.context import SnapshotValidationContext
        from app.application.worldSnapshot.service.worldSnapshotService import WorldSnapshotService, _ApplyRefused
        from app.dataModel.patch.results.sectionResult import SectionApplyReceipt, SectionRefused
        from app.dataModel.patch.sections.section import SectionHeader
        from app.dataModel.registryKey import RegistryKey
        from app.dataModel.patch.registry.sectionMetadata import PatchSectionRegistry
        from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
        from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata
        from tests.snapshotCore.support.fixtures import STAMP

        async def check(mode):
            async with live_database() as bundle, live_database(bundle[0].path, seed=False) as peer:
                _, commits, world, _, history, operations = bundle
                base = await live_started(bundle)
                before = base
                if mode == "conflict":
                    base = base.model_copy(update={"publication_id": "stale-expectation"})
                op = "candidate"
                await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, op, "w1", "a"*64, "b"*64)
                assigned = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="candidate-world")
                registry = Mock(spec=SectionRegistry)
                service = WorldSnapshotService(registry, world)
                sections = []
                handlers = []
                targets = []

                outer_scope = None
                refused = SectionRefused(category=SnapshotApplyOutcomeKind.REJECTED,
                    diagnostics=(FieldPathError(path=("two",), message="refused"),))
                conflict = SectionRefused(category=SnapshotApplyOutcomeKind.CONFLICT,
                    diagnostics=(FieldPathError(path=(), message="world publication changed"),))
                faults = {"metadata_error": PublicationInfrastructureError("after append"),
                          "metadata_cancel": asyncio.CancelledError("after append")}

                async def apply(section, ctx):
                    self.assertIs(ctx.scope, outer_scope)
                    targets.append(ctx.next_publication)
                    await operations._access.insert(ctx.scope, PublicationOperationRow(
                        f"marker-{section.header.key}", "w1", OperationKind.SNAPSHOT_APPLY.value, "a" * 64))
                    if mode == "refuse" and section.header.key == "two":
                        return refused
                    return SectionApplyReceipt(section_key=section.header.key, state_refs=(), history_refs=(),
                                               retained_artifacts=(), changed=())

                for key in ("one", "two", "three"):
                    header = SectionHeader(key=RegistryKey[PatchSectionRegistry](key), format_version=1, depends_on=())
                    sections.append(Mock(header=header))
                    handler = Mock(spec=BoundSectionHandler)
                    handler.apply = AsyncMock(side_effect=apply)
                    handlers.append(handler)
                registry.resolve.side_effect = handlers

                async def execute():
                    nonlocal outer_scope
                    async with commits.transaction(op) as scope:
                        outer_scope = scope
                        validation = SnapshotValidationContext(op, base, (), (), scope.read_scope)
                        async with service._apply_to_target(scope, validation, tuple(sections), assigned, ()) as (ctx, receipts):
                            await history.append(scope, WorldSnapshotMetadata(ref=assigned, parent=base.snapshot_head,
                                operation_id=op, turn_id=1, created_at=STAMP, envelope_format_version=1,
                                base_pack_hash=base.pack_hash, state_refs=(), history_refs=(), retained_artifacts=()), receipts)
                            if mode in faults:
                                raise faults[mode]

                with patch.object(world, "compare_append", wraps=world.compare_append) as cas:
                    if mode == "success":
                        await execute()
                    elif mode in faults:
                        with self.assertRaises(type(faults[mode])) as error:
                            await execute()
                        self.assertIs(error.exception, faults[mode])
                    else:
                        with self.assertRaises(_ApplyRefused) as error:
                            await execute()
                        self.assertEqual(error.exception.refusal, refused if mode == "refuse" else conflict)
                    self.assertEqual(len(targets), 2 if mode == "refuse" else 3)
                    self.assertTrue(all(target is targets[0] for target in targets))
                    if mode == "refuse":
                        handlers[2].apply.assert_not_awaited()
                    if mode == "refuse" or mode in faults:
                        cas.assert_not_awaited()
                    else:
                        self.assertIs(cas.await_args.args[2], targets[0])
                self.assertEqual(await peer[2].read("w1"), targets[0] if mode == "success" else before)
                self.assertEqual((await peer[4].read(assigned)) is not None, mode == "success")
                async with peer[0].conn.execute("SELECT name FROM worlds WHERE world_uid='w1'") as cur:
                    self.assertEqual((await cur.fetchone())[0], "w1")
                async with peer[0].conn.execute("SELECT operation_id FROM publication_operations "
                                                "WHERE operation_id LIKE 'marker-%' ORDER BY operation_id") as cur:
                    self.assertEqual([row[0] for row in await cur.fetchall()],
                                     ["marker-one", "marker-three", "marker-two"] if mode == "success" else [])
        for mode in ("success", "refuse", "conflict", "metadata_error", "metadata_cancel"):
            with self.subTest(mode=mode):
                run_async(check(mode))
