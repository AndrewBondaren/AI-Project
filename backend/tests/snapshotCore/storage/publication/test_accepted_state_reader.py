import unittest
from unittest.mock import AsyncMock

from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.service.acceptedStateReader import AcceptedStateReader, PublicationMismatch, StateReadFailure
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult, SnapshotCommitRefs
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef
from tests.snapshotCore.storage.publication.test_history import KEY, OTHER, envelope, receipt
from tests.snapshotCore.support.fixtures import live_database, live_started, run_async


async def publish(bundle, base, operation, snapshot, state, receipts):
    _, commits, publications, _, history, operations = bundle
    await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, operation, "w1", "a" * 64, "b" * 64)
    target = base.model_copy(update={"publication_id": operation + "-pub", "snapshot_head": snapshot})
    async with commits.transaction(operation) as scope:
        await history.append(scope, envelope(snapshot, operation=operation, parent=base.snapshot_head,
                                             states=(state,)), receipts)
        await publications.compare_append(scope, base, target)
        await operations.record_terminal(scope, SnapshotApplyResult(
            operation_id=operation, request_fingerprint="b" * 64, category=SnapshotApplyOutcomeKind.COMMITTED,
            diagnostics=(), committed=SnapshotCommitRefs(world_snapshot=snapshot, player_snapshots=(), publication=target)))
    return target


class AcceptedStateReaderTests(unittest.TestCase):
    def test_retained_publication_and_snapshot_addresses(self):
        async def check():
            async with live_database() as reader_db:
                initial = await live_started(reader_db)
                db, commits, publications, _, history, _ = reader_db
                reader = AcceptedStateReader(publications, history)
                async with commits.read_scope() as scope:
                    self.assertEqual(await reader.resolve_publication(initial, KEY, scope), initial)

                snapshot = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="s")
                state = SectionStateRef(snapshot=snapshot, section_key=KEY, format_version=1)
                child = snapshot.model_copy(update={"snapshot_id": "child"})
                async with live_database(db.path, seed=False) as writer_db:
                    target = await publish(writer_db, initial, "op", snapshot, state, (receipt(states=(state,)),))
                    inherited = await publish(writer_db, target, "next", child, state, ())

                for publication, address in ((initial, initial), (target, state), (inherited, state)):
                    async with commits.read_scope() as scope:
                        self.assertEqual(await reader.resolve_publication(publication, KEY, scope), address)
                async with commits.read_scope() as scope:
                    self.assertEqual(await reader.resolve_snapshot(snapshot, KEY, scope), state)
                    self.assertEqual(await reader.resolve_snapshot(child, KEY, scope), state)
                    self.assertEqual(await reader.resolve_snapshot(child, OTHER, scope), StateReadFailure.MISSING_SECTION)
                    missing = snapshot.model_copy(update={"snapshot_id": "absent"})
                    self.assertEqual(await reader.resolve_snapshot(missing, KEY, scope), StateReadFailure.MISSING_SNAPSHOT)
                    for field, value in (("world_uid", "foreign"), ("timeline_id", "other")):
                        with self.assertRaises(PublicationInfrastructureError):
                            await reader.resolve_snapshot(snapshot.model_copy(update={field: value}), KEY, scope)
                    foreign = initial.model_copy(update={"world_uid": "foreign"})
                    self.assertEqual(await reader.resolve_publication(foreign, KEY, scope), StateReadFailure.MISSING_PUBLICATION)
                    forged = target.model_copy(update={"active_timeline_id": "other"})
                    self.assertEqual(await reader.resolve_publication(forged, KEY, scope), PublicationMismatch(target))
                    pregame = await publications.read_exact("w1", "active", scope=scope)
                    self.assertEqual(await reader.resolve_publication(pregame, KEY, scope), StateReadFailure.GAMEPLAY_NOT_STARTED)
        run_async(check())

    def test_accepted_branch_point_uses_publication_binding(self):
        async def check():
            async with live_database() as bundle:
                initial = await live_started(bundle)
                head = WorldSnapshotRef(world_uid="w1", timeline_id="t1", snapshot_id="parent")
                branch = initial.model_copy(update={"publication_id": "branch", "snapshot_head": head,
                                                    "active_timeline_id": "child"})
                publications, history = AsyncMock(), AsyncMock()
                publications.read_exact.return_value = branch
                async with bundle[1].read_scope() as scope:
                    reader = AcceptedStateReader(publications, history)
                    self.assertEqual(await reader.resolve_publication(branch, KEY, scope), branch)
                    publications.read_exact.assert_awaited_once_with("w1", "branch", scope=scope)
                    history.read.assert_not_awaited()
        run_async(check())
