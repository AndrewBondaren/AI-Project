"""Service admission mapping with real independent SQLite connections."""
from tests.snapshotCore.support.mockRequestCodec import mock_request_codec
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.publication.errors import OperationBindingMismatchError, OperationBusyError
from app.application.worldSnapshot.errors import SnapshotOperationCancelledError
from app.application.worldSnapshot.service.worldSnapshotService import WorldSnapshotService
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from tests.snapshotCore.support.publicationBinding import SnapshotTestResult
from tests.snapshotCore.support.fakeSection import FakeSectionRefused
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyCode, SnapshotApplyRelationIssue
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.db.repositories.sqlite.artifacts.leaseStore import SqliteArtifactLeases
from tests.snapshotCore.support.artifactFixtures import adapters
from tests.snapshotCore.support.diagnostics import target_issue
from tests.snapshotCore.support.fixtures import live_database, run_async


class SnapshotClaimMappingTests(unittest.TestCase):
    def test_mismatch_is_typed_nonmutating_and_separate_from_terminal_refusal(self):
        async def check():
            async with live_database() as bundle, live_database(bundle[0].path, seed=False) as peer:
                _, _, world, players, history, operations = bundle
                service = WorldSnapshotService(registry := SectionRegistry(FakeSectionRefused), world, players, history,
                    publication_binding=operations.result_binding, operations=operations, request_codec=mock_request_codec(registry))
                owner = await service._claim_publication("claim", "w1", "a"*64, "b"*64)
                before = await peer[-1].read("claim")
                with self.assertRaises(OperationBusyError):
                    await service._claim_publication("claim", "w1", "a"*64, "b"*64)
                for uid, prep, request in (("w2", "a"*64, "b"*64), ("w1", "c"*64, "b"*64),
                                           ("w1", "a"*64, "c"*64)):
                    with self.assertRaises(OperationBindingMismatchError) as caught:
                        await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, "claim", uid, prep, request)
                    facts = caught.exception.mismatch
                    self.assertEqual(facts.stored_request_fingerprint, "b"*64)
                    self.assertEqual(facts.requested_request_fingerprint, request)
                    result = await service._claim_publication("claim", uid, prep, request)
                    self.assertEqual(result.category, SnapshotApplyOutcomeKind.REJECTED)
                    self.assertEqual(result.request_fingerprint, request)
                    self.assertEqual(result.diagnostics[0].code, SnapshotApplyCode.OPERATION_BINDING_MISMATCH)
                    self.assertEqual(await peer[-1].read("claim"), before)
                failure = ValueError("an unrelated invariant")
                with patch.object(operations, "claim_publication", side_effect=failure):
                    with self.assertRaises(ValueError) as caught:
                        await service._claim_publication("claim", "w1", "a"*64, "b"*64)
                    self.assertIs(caught.exception, failure)
                refusal = SnapshotTestResult(category=SnapshotApplyOutcomeKind.REJECTED, operation_id="claim",
                    request_fingerprint="b"*64, committed=None, diagnostics=(target_issue("domain refused"),
                        SnapshotApplyRelationIssue(code=SnapshotApplyCode.GAMEPLAY_NOT_STARTED,
                                                   section_key=None, player_uid=None, artifact=None)))
                await operations.record_refusal(owner, refusal)
                self.assertEqual((await peer[-1].read("claim")).terminal, refusal)
                with patch.object(history, "read", new_callable=AsyncMock) as read:
                    self.assertEqual(await service._claim_publication("claim", "w1", "a"*64, "b"*64), refusal)
                    read.assert_not_awaited()
                result = await service._claim_publication("claim", "w1", "a"*64, "c"*64)
                self.assertEqual(result.diagnostics[0].code, SnapshotApplyCode.OPERATION_BINDING_MISMATCH)
                self.assertEqual((await peer[-1].read("claim")).terminal, refusal)
        run_async(check())

    def test_cancel_replay_preserves_absent_or_existing_request_binding(self):
        async def check():
            async with live_database() as bundle, live_database(bundle[0].path, seed=False) as peer:
                catalog, _ = adapters(bundle)
                operations = bundle[-1]
                leases = SqliteArtifactLeases(catalog._scopes, operations, operations._artifacts)
                service = WorldSnapshotService(registry := SectionRegistry(FakeSectionRefused), bundle[2], bundle[3], bundle[4],
                    publication_binding=operations.result_binding, operations=operations, request_codec=mock_request_codec(registry))
                for bound in (False, True):
                    op = "bound" if bound else "early"
                    lease = await leases.open_operation(op, "w1", OperationKind.SNAPSHOT_APPLY, "a"*64)
                    if bound:
                        await leases.finish_preparation(lease, ())
                        await service._claim_publication(op, "w1", "a"*64, "b"*64)
                    cancelled = await leases.cancel(op, lease.fence)
                    for request in ("b"*64, "c"*64):
                        if bound and request != "b"*64:
                            result = await service._claim_publication(op, "w1", "a"*64, request)
                            self.assertEqual(result.category, SnapshotApplyOutcomeKind.REJECTED)
                        else:
                            with self.assertRaises(SnapshotOperationCancelledError) as caught:
                                await service._claim_publication(op, "w1", "a"*64, request)
                            self.assertEqual(caught.exception.outcome, cancelled.terminal)
                        observed = await peer[-1].read(op)
                        self.assertEqual(observed, cancelled)
                        self.assertEqual(observed.publication_fingerprint, "b"*64 if bound else None)
                    result = await service._claim_publication(op, "w1", "d"*64, "b"*64)
                    self.assertEqual(result.category, SnapshotApplyOutcomeKind.REJECTED)
                invocation = asyncio.CancelledError()
                with patch.object(operations, "claim_publication", side_effect=invocation):
                    with self.assertRaises(asyncio.CancelledError) as caught:
                        await service._claim_publication("early", "w1", "a"*64, "b"*64)
                    self.assertIs(caught.exception, invocation)
                with self.assertRaises(ValidationError):
                    SnapshotOperationCancelledError(cancelled.terminal.model_copy(update={"operation_id": ""}))
        run_async(check())
