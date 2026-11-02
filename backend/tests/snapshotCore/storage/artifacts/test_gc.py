"""DDL live-set/representation gates; no physical deletion or scheduler."""

import sqlite3
import asyncio
import unittest
from app.application.publication.errors import PublicationInfrastructureError
from app.dataModel.artifacts.lifecycle.holders import OperationHolder, ArtifactRetentionHolder, SnapshotHolder
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.worldSnapshot.identity.refs import SnapshotChainKind
from app.db.repositories.sqlite.artifacts.catalogStore import SqliteArtifactCatalog
from app.db.repositories.sqlite.artifacts.holderStore import SqliteArtifactHolders
from app.db.repositories.sqlite.artifacts.access.artifactScope import SqliteArtifactScope
from tests.snapshotCore.support.fixtures import live_database, run_async, live_started, unsafe_update
from tests.snapshotCore.support.artifactFixtures import (
    adapters, descriptor, preparing, writer_fact, sealed, close_preparation, snapshot_metadata,
)
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


class SqliteArtifactAdapterTests(unittest.TestCase):
    def test_two_connection_reserve_race_shares_one_identity_and_both_holds(self):
        async def check():
            async with live_database() as first:
                async with live_database(first[0].path, seed=False) as second:
                    catalog, holders = adapters(first)
                    other, _ = adapters(second)
                    a, b = await preparing(first, "first"), await preparing(second, "second")
                    left, right = await asyncio.gather(catalog.reserve(a, descriptor()), other.reserve(b, descriptor()))
                    self.assertEqual(left.artifact_id, right.artifact_id)
                    self.assertEqual(set(await holders.holders(descriptor())), {OperationHolder(lease=a), OperationHolder(lease=b)})
        run_async(check())

    def test_reserve_dedupes_full_descriptor_and_fenced_operations(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                first, second = await preparing(bundle), await preparing(bundle, "second")
                for ref in (descriptor(), descriptor("rows", rows=True)):
                    a = await catalog.reserve(first, ref)
                    b = await catalog.reserve(second, ref)
                    self.assertEqual(a.artifact_id, b.artifact_id)
                    self.assertEqual(await catalog.reserve(first, ref), a)
                    self.assertEqual(await catalog.read(ref), ref)
                    self.assertEqual(set(await holders.holders(ref)), {OperationHolder(lease=first), OperationHolder(lease=second)})
                    self.assertFalse(await catalog.is_sealed(ref))
                    with self.assertRaises(ValueError):
                        await catalog.reserve(first, ref.model_copy(update={"nbytes": ref.nbytes + 1}))
                for invalid in (first.model_copy(update={"fence": 2}), first.model_copy(update={"world_uid": "other"})):
                    with self.assertRaises(ValueError):
                        await catalog.reserve(invalid, descriptor("new"))
                with self.assertRaises(ValueError):
                    await catalog.reserve(first, descriptor().model_copy(update={"nbytes": True}))
                async with catalog.guard(descriptor()):
                    self.assertTrue(await holders.is_held(descriptor(), OperationHolder(lease=first)))
        run_async(check())


class SqliteArtifactBoundaryTests(unittest.TestCase):
    def test_catalog_and_storage_rows_reject_each_corrupt_field(self):
        async def check():
            async with live_database() as bundle:
                catalog, _ = adapters(bundle)
                lease = await preparing(bundle)
                reservation = await sealed(bundle, catalog, lease, descriptor())
                cases = {
                    "artifact_id": " bad ", "kind": "unknown", "format_key": "", "format_version": 0,
                    "content_hash": "invalid", "nbytes": -1, "row_count": 0,
                }
                for column, bad in cases.items():
                    with self.subTest(table="catalog", column=column):
                        old = await unsafe_update(bundle[0], "artifact_catalog", "artifact_id", reservation.artifact_id, column, bad)
                        try:
                            async with bundle[1].read_scope() as scope:
                                with self.assertRaises(PublicationInfrastructureError):
                                    await catalog._by_id(scope, bad if column == "artifact_id" else reservation.artifact_id)
                        finally:
                            await unsafe_update(bundle[0], "artifact_catalog", "artifact_id",
                                bad if column == "artifact_id" else reservation.artifact_id, column, old)
                async with bundle[1].read_scope() as scope:
                    row = await catalog._storage(scope, reservation.artifact_id)
                for column, bad in {"event_id": " bad ", "artifact_id": " bad ", "predecessor_id": "missing",
                                    "event_seq": 0, "kind": "unknown"}.items():
                    with self.subTest(table="storage", column=column):
                        old = await unsafe_update(bundle[0], "artifact_storage_events", "event_id", row.event_id, column, bad)
                        try:
                            async with bundle[1].read_scope() as scope:
                                with self.assertRaises(PublicationInfrastructureError):
                                    await catalog._storage(scope, bad if column == "artifact_id" else reservation.artifact_id)
                        finally:
                            await unsafe_update(bundle[0], "artifact_storage_events", "event_id",
                                bad if column == "event_id" else row.event_id, column, old)
        run_async(check())

    def test_holder_rows_reject_each_corrupt_field_and_owner_branch(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                reservation = await catalog.reserve(lease, descriptor())
                async with bundle[1].read_scope() as scope:
                    row = (await holders._chain(holders._access, scope, reservation.artifact_id))[0]
                cases = {"event_id": " bad ", "artifact_id": " bad ", "holder_kind": "unknown",
                    "operation_id": "missing", "fence": 0, "retained_artifact_id": "missing",
                    "world_snapshot_id": "missing", "player_snapshot_id": "missing",
                    "predecessor_id": "missing", "event_seq": 0, "event_kind": "unknown"}
                for column, bad in cases.items():
                    with self.subTest(column=column):
                        old = await unsafe_update(bundle[0], "artifact_holder_events", "event_id", row.event_id, column, bad)
                        try:
                            async with bundle[1].read_scope() as scope:
                                with self.assertRaises(PublicationInfrastructureError):
                                    latest = await holders._chain(holders._access, scope,
                                        bad if column == "artifact_id" else reservation.artifact_id)
                                    for event in latest:
                                        await holders._hydrate(scope, event)
                        finally:
                            await unsafe_update(bundle[0], "artifact_holder_events", "event_id",
                                bad if column == "event_id" else row.event_id, column, old)
        run_async(check())

class SqliteArtifactBehaviorTests(unittest.TestCase):
    def test_seal_requires_exact_reservation_writer_hold_and_admission(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease, other = await preparing(bundle), await preparing(bundle, "other")
                reservation = await catalog.reserve(lease, descriptor())
                foreign = await catalog.reserve(other, descriptor())
                await writer_fact(bundle, foreign)
                with self.assertRaises(ValueError):
                    await catalog.seal(reservation)
                await writer_fact(bundle, reservation)
                with self.assertRaises(ValueError):
                    await catalog.seal(reservation.model_copy(update={"artifact_id": "wrong"}))
                self.assertEqual(await catalog.seal(reservation), reservation.ref)
                self.assertEqual(await catalog.seal(reservation), reservation.ref)
                await close_preparation(bundle, lease)
                with self.assertRaises(ValueError):
                    await catalog.seal(reservation)
                with self.assertRaises(ValueError):
                    await holders.release(reservation.ref, OperationHolder(lease=lease))
                await writer_fact(bundle, reservation, release=True)
                await holders.release(reservation.ref, OperationHolder(lease=lease))
                self.assertTrue(await catalog.is_sealed(reservation.ref))
        run_async(check())

    def test_guarded_gc_no_first_seal_repeat_and_reseal(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                ref, unsealed = descriptor(), descriptor("never sealed")
                original = await sealed(bundle, catalog, lease, ref)
                await catalog.reserve(lease, unsealed)
                with self.assertRaises(ValueError):
                    await catalog.mark_deleted(ref)
                await close_preparation(bundle, lease)
                for item in (ref, unsealed):
                    await holders.release(item, OperationHolder(lease=lease))
                    await holders.release(item, OperationHolder(lease=lease))
                    async with catalog.guard(item):
                        await catalog.mark_deleted(item)
                        await catalog.mark_deleted(item)
                    self.assertFalse(await catalog.is_sealed(item))
                    self.assertEqual(await catalog.read(item), item)
                retry = await preparing(bundle, "retry")
                current = await sealed(bundle, catalog, retry, ref)
                self.assertEqual(current.artifact_id, original.artifact_id)
                self.assertTrue(await catalog.is_sealed(ref))
                async with live_database(bundle[0].path, seed=False) as reopened:
                    again, held = adapters(reopened)
                    self.assertTrue(await again.is_sealed(ref))
                    self.assertTrue(await held.is_held(ref, OperationHolder(lease=retry)))
        run_async(check())

    def test_retention_requires_sealed_owner_and_preserves_operation_independence(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                ref, owner = descriptor(), descriptor("manifest")
                await sealed(bundle, catalog, lease, ref)
                reservation = await catalog.reserve(lease, owner)
                holder = ArtifactRetentionHolder(artifact=owner)
                with self.assertRaises(ValueError):
                    await holders.acquire(ref, holder)
                await writer_fact(bundle, reservation)
                await catalog.seal(reservation)
                await writer_fact(bundle, reservation, release=True)
                await holders.acquire(ref, holder)
                await holders.acquire(ref, holder)
                await close_preparation(bundle, lease)
                await holders.release(ref, OperationHolder(lease=lease))
                self.assertEqual(await holders.holders(ref), (holder,))
                with self.assertRaises(ValueError):
                    await catalog.mark_deleted(ref)
                await holders.release(ref, holder)
                self.assertEqual(await holders.holders(ref), ())
                await holders.acquire(ref, holder)
                self.assertEqual(await holders.holders(ref), (holder,))
        run_async(check())

    def test_handoff_maps_metadata_per_snapshot_and_borrows_parent_transaction(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                a, b, c, leftover = (descriptor(n) for n in ("a", "b", "c", "leftover"))
                for ref in (a, b, c, leftover):
                    await sealed(bundle, catalog, lease, ref)
                await close_preparation(bundle, lease, ready=True)
                await bundle[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, lease.operation_id, "w1", "a" * 64, "b" * 64)
                with self.assertRaisesRegex(RuntimeError, "parent rollback"):
                    async with bundle[1].transaction(lease.operation_id) as scope:
                        snapshots = await snapshot_metadata(bundle, scope, lease, (a, b), (b, c))
                        await holders.handoff(scope, lease, snapshots, (a, b, c))
                        async with holders._scopes.bind(scope):
                            self.assertEqual(set(await holders.holders(b)), {SnapshotHolder(snapshot=s) for s in snapshots})
                        scope.assert_active()
                        raise RuntimeError("parent rollback")
                self.assertEqual(await holders.holders(a), (OperationHolder(lease=lease),))
                async with bundle[1].transaction(lease.operation_id) as scope:
                    snapshots = await snapshot_metadata(bundle, scope, lease, (a, b), (b, c))
                    await holders.handoff(scope, lease, snapshots, (a, b, c))
                    await holders.handoff(scope, lease, snapshots, (a, b, c))
                self.assertEqual(await holders.holders(a), (SnapshotHolder(snapshot=snapshots[0]),))
                self.assertEqual(await holders.holders(c), (SnapshotHolder(snapshot=snapshots[1]),))
                self.assertEqual(await holders.holders(leftover), (OperationHolder(lease=lease),))
                with self.assertRaises(ValueError):
                    await holders.release(a, SnapshotHolder(snapshot=snapshots[0]))
        run_async(check())

    def test_handoff_missing_destination_refuses_before_any_release(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                a, missing = descriptor("a"), descriptor("missing destination")
                for ref in (a, missing):
                    await sealed(bundle, catalog, lease, ref)
                await close_preparation(bundle, lease, ready=True)
                await bundle[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, lease.operation_id, "w1", "a" * 64, "b" * 64)
                async with bundle[1].transaction(lease.operation_id) as scope:
                    snapshots = await snapshot_metadata(bundle, scope, lease, (a,))
                    with self.assertRaises(ValueError):
                        await holders.handoff(scope, lease, snapshots, (a, missing))
                    async with holders._scopes.bind(scope):
                        self.assertEqual(await holders.holders(a), (OperationHolder(lease=lease),))
                with self.assertRaises(PublicationInfrastructureError):
                    await holders.handoff(scope, lease, (), (a,))
        run_async(check())

    def test_ready_inactive_handoff_requires_explicit_existing_retention(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                a, owner = descriptor(), descriptor("manifest")
                for ref in (a, owner):
                    await sealed(bundle, catalog, lease, ref)
                await close_preparation(bundle, lease, ready=True)
                await bundle[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, lease.operation_id, "w1", "a" * 64, "b" * 64)
                async with bundle[1].transaction(lease.operation_id) as scope:
                    with self.assertRaises(ValueError):
                        await holders.handoff(scope, lease, (), (a,))
                retained = ArtifactRetentionHolder(artifact=owner)
                await holders.acquire(a, retained)
                async with bundle[1].transaction(lease.operation_id) as scope:
                    await holders.handoff(scope, lease, (), (a,))
                self.assertEqual(await holders.holders(a), (retained,))
                self.assertTrue(await holders.is_held(owner, OperationHolder(lease=lease)))
        run_async(check())

    def test_history_resolves_exact_world_player_refs_without_envelope_decode(self):
        async def check():
            async with live_database() as bundle:
                await live_started(bundle)
                lease = await preparing(bundle)
                await close_preparation(bundle, lease, ready=True)
                await bundle[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, lease.operation_id, "w1", "a" * 64, "b" * 64)
                async with bundle[1].transaction(lease.operation_id) as scope:
                    snapshots = await snapshot_metadata(bundle, scope, lease, (), ())
                    for ref in snapshots:
                        self.assertEqual(await bundle[4].resolve_ref(ref.snapshot_id, ref.kind, scope=scope.read_scope), ref)
                    self.assertIsNone(await bundle[4].resolve_ref("missing", SnapshotChainKind.WORLD, scope=scope.read_scope))
                    with self.assertRaises(ValueError):
                        await bundle[4].resolve_ref("missing", "bogus", scope=scope.read_scope)
                with self.assertRaises(PublicationInfrastructureError):
                    await bundle[4].resolve_ref(snapshots[0].snapshot_id, snapshots[0].kind, scope=scope.read_scope)
                await unsafe_update(bundle[0], "world_snapshots", "snapshot_id", snapshots[0].snapshot_id, "snapshot_data", b"not an envelope")
                async with bundle[1].read_scope() as read:
                    self.assertEqual(await bundle[4].resolve_ref(snapshots[0].snapshot_id, snapshots[0].kind, scope=read), snapshots[0])
                for table, key, ref, column in (("world_snapshots", "snapshot_id", snapshots[0], "world_uid"),
                        ("world_snapshots", "snapshot_id", snapshots[0], "timeline_id"),
                        ("player_snapshots", "player_snapshot_id", snapshots[1], "player_uid")):
                    old = await unsafe_update(bundle[0], table, key, ref.snapshot_id, column, " bad ")
                    try:
                        async with bundle[1].read_scope() as read:
                            with self.assertRaises(PublicationInfrastructureError):
                                await bundle[4].resolve_ref(ref.snapshot_id, ref.kind, scope=read)
                    finally:
                        await unsafe_update(bundle[0], table, key, ref.snapshot_id, column, old)
        run_async(check())

    def test_handoff_refuses_wrong_scope_fence_live_writers_and_unknown_transfer(self):
        async def check():
            async with live_database() as bundle:
                catalog, holders = adapters(bundle)
                lease = await preparing(bundle)
                ref = descriptor()
                await sealed(bundle, catalog, lease, ref)
                await close_preparation(bundle, lease, ready=True)
                await bundle[-1].claim_publication(OperationKind.SNAPSHOT_APPLY, lease.operation_id, "w1", "a" * 64, "b" * 64)
                await holders.acquire(ref, ArtifactRetentionHolder(artifact=ref))
                async with bundle[1].transaction("wrong operation") as scope:
                    with self.assertRaises(ValueError):
                        await holders.handoff(scope, lease, (), (ref,))
                async with bundle[1].transaction(lease.operation_id) as scope:
                    with self.assertRaises(PublicationInfrastructureError):
                        await holders.handoff(scope.read_scope, lease, (), (ref,))
                    with self.assertRaises(ValueError):
                        await holders.handoff(scope, lease.model_copy(update={"fence": 2}), (), (ref,))
                    with self.assertRaises(ValueError):
                        await holders.handoff(scope, lease, (), (ref, ref))
                self.assertTrue(await holders.is_held(ref, OperationHolder(lease=lease)))
                # A different operation's live writer blocks only that operation's release;
                # release still requires the whole matching operation/fence to drain.
                other = await preparing(bundle, "other")
                reservation = await catalog.reserve(other, ref)
                await writer_fact(bundle, reservation)
                await close_preparation(bundle, other)
                async with bundle[1].transaction(other.operation_id) as scope:
                    with self.assertRaises(ValueError):
                        await holders.handoff(scope, other, (), (ref,))
                self.assertTrue(await holders.is_held(ref, OperationHolder(lease=other)))
        run_async(check())

    def test_adapter_di_rejects_foreign_coordinators_and_reader(self):
        async def check():
            async with live_database() as first:
                async with live_database(first[0].path, seed=False) as second:
                    scopes = SqliteArtifactScope(first[1], first[2]._access)
                    with self.assertRaises(ValueError):
                        SqliteArtifactCatalog(scopes, second[-1], first[-1]._artifacts)
                    with self.assertRaises(ValueError):
                        SqliteArtifactCatalog(scopes, first[-1], second[-1]._artifacts)
                    with self.assertRaises(ValueError):
                        SqliteArtifactHolders(scopes, first[-1], first[-1]._artifacts, second[4])
        run_async(check())
