"""Synthetic participants through Snapshot seams and a real SQLite transaction owner."""
import unittest
from unittest.mock import AsyncMock, Mock, patch
from contextlib import nullcontext

from app.application.patch.registry.sectionRegistry import SectionRegistry, BoundSectionHandler
from app.application.publication.errors import PublicationInfrastructureError, UnknownCommitOutcome
from app.application.worldSnapshot.errors import SnapshotReceiptContractError
from app.application.worldSnapshot.service.worldSnapshotService import (
    WorldSnapshotService, _SnapshotValidationRefused, _ApplyRefused,
)
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionApplyReceipt
from app.dataModel.worldSnapshot.results.apply import SnapshotCommitRefs
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.db.models.snapshotCore.operationRows import PublicationOperationRow
from tests.snapshotCore.support.fakeSection import HeaderOnlyPatch, FakeTargetIssue, FakeSectionRefused
from tests.snapshotCore.support.publicationBinding import SnapshotTestResult
from tests.snapshotCore.support.diagnostics import target_issue
from tests.snapshotCore.support.fixtures import live_database, live_started, live_tick, run_async, STAMP


class AttemptTransactionTests(unittest.TestCase):
    def test_sequence_rollback_unknown_and_exact_replay(self):
        async def check(mode):
            async with live_database() as bundle, live_database(bundle[0].path, seed=False) as peer:
                _, commits, world, players, history, operations = bundle
                await live_started(bundle)
                await live_tick(bundle)
                expected = await world.read("w1")
                assigned = expected.snapshot_head.model_copy(update={"snapshot_id": "attempt-world"})
                sections = tuple(DomainSection[HeaderOnlyPatch](
                    header=SectionHeader(key=key, format_version=1, depends_on=()),
                    patches=(HeaderOnlyPatch(header=PatchHeader(
                        ref=PatchRef(operation_id="attempt", section_key=key, ordinal=0),
                        format_version=1, depends_on=(), artifacts=())),)) for key in ("one", "two", "three"))
                request = PatchSet[DomainSection[HeaderOnlyPatch]](format_version=1, operation_id="attempt",
                    preparation_fingerprint="a" * 64, world_uid="w1", timeline_id="t1", turn_id=2,
                    expected_world=expected, expected_players=(), sections=sections)
                trace, views, scopes = [], [], []
                refusal = FakeSectionRefused(category=SnapshotApplyOutcomeKind.REJECTED,
                    diagnostics=(target_issue("synthetic refusal"),))

                async def validate(section, context):
                    trace.append("validate:" + section.header.key)
                    views.append(context.admitted_sections)
                    context.admitted_sections.require(section.header.key, model=type(section))
                    return refusal if mode == "validate_refusal" and section.header.key == "two" else SectionAccepted()

                async def apply(section, context):
                    trace.append("apply:" + section.header.key)
                    self.assertIs(context.validation.admitted_sections, views[0])
                    await operations._access.insert(context.scope, PublicationOperationRow(
                        "marker-" + section.header.key, "w1", OperationKind.SNAPSHOT_APPLY.value, "a" * 64))
                    if mode == "apply_refusal" and section.header.key == "two":
                        return refusal
                    bad = mode in ("receipt_fault", "rollback_unknown") and section.header.key == "two"
                    return SectionApplyReceipt(section_key=section.header.key, states=(), history=(),
                        changed=(section.patches[0].header.ref.model_copy(update={"ordinal": 9}),) if bad else ())

                handler = Mock(spec=BoundSectionHandler)
                handler.validate = AsyncMock(side_effect=validate)
                handler.apply = AsyncMock(side_effect=apply)
                registry = Mock(spec=SectionRegistry)
                registry.diagnostic_types = frozenset({FakeTargetIssue})
                registry.resolve.return_value = handler
                service = WorldSnapshotService(registry, world, players, history,
                    publication_binding=operations.result_binding, operations=operations)
                read = history.read
                append = history.append
                in_storage_append = False
                async def append_metadata(*args, **kwargs):
                    nonlocal in_storage_append
                    in_storage_append = True
                    try:
                        return await append(*args, **kwargs)
                    finally:
                        in_storage_append = False
                async def read_base(ref, *, scope=None):
                    trace.append("storage-base" if in_storage_append else "base")
                    if mode == "missing_base":
                        return None
                    return await read(ref, scope=scope)

                async def attempt():
                    claim = await service._claim_publication("attempt", "w1", "a" * 64, "b" * 64)
                    if isinstance(claim, SnapshotTestResult):
                        return claim
                    async with commits.transaction("attempt") as scope:
                        scopes.append(scope)
                        self.assertIs(scope.read_scope, scope.read_scope)
                        validation = await service._validate_sections(request, scope=scope.read_scope, resolved_dependencies=())
                        bases = await service._load_pinned_bases(validation, scope=scope.read_scope, source_bases={})
                        async with service._apply_to_target(scope, validation, request.sections, assigned, (),
                                bases=bases, request=request) as (context, receipts):
                            trace.append("metadata")
                            await service._append_metadata(context, 2, STAMP, receipts, bases=bases)
                        trace.append("terminal")
                        result = SnapshotTestResult(category=SnapshotApplyOutcomeKind.COMMITTED,
                            operation_id="attempt", request_fingerprint="b" * 64,
                            committed=SnapshotCommitRefs(world_snapshot=assigned, player_snapshots=(),
                                publication=context.next_publication), diagnostics=())
                        await operations.record_terminal(scope, result)
                    trace.append("committed")
                    return result

                commit = commits.driver.commit
                async def lost_commit(conn):
                    # Claim occurs in its own transaction; inject only into the attempt.
                    if not scopes:
                        return await commit(conn)
                    if mode == "commit_unknown_applied":
                        await commit(conn)
                    raise OSError("lost commit acknowledgement")

                fault = (patch.object(commits.driver, "rollback", side_effect=OSError("lost rollback acknowledgement"))
                    if mode == "rollback_unknown" else patch.object(commits.driver, "commit", side_effect=lost_commit)
                    if mode.startswith("commit_unknown") else nullcontext())
                with patch.object(history, "read", side_effect=read_base), patch.object(history, "append", side_effect=append_metadata), fault:
                    if mode == "success":
                        result = await attempt()
                    else:
                        error = (_SnapshotValidationRefused if mode == "validate_refusal" else
                            _ApplyRefused if mode == "apply_refusal" else
                            UnknownCommitOutcome if "unknown" in mode else
                            SnapshotReceiptContractError if mode == "receipt_fault" else PublicationInfrastructureError)
                        with self.assertRaises(error):
                            await attempt()
                validations = ["validate:one", "validate:two", "validate:three"]
                self.assertEqual(trace[:3], validations)
                self.assertTrue(all(view is views[0] for view in views))
                if mode == "validate_refusal":
                    self.assertEqual(trace, validations)
                elif mode == "missing_base":
                    self.assertEqual(trace, validations + ["base"])
                elif mode in ("receipt_fault", "rollback_unknown", "apply_refusal"):
                    self.assertEqual(trace, validations + ["base", "apply:one", "apply:two"])
                else:
                    self.assertEqual(trace, validations + ["base", "apply:one", "apply:two", "apply:three",
                        "metadata", "storage-base", "terminal"] + (["committed"] if mode == "success" else []))
                published = mode in ("success", "commit_unknown_applied")
                self.assertEqual((await peer[2].read("w1")).snapshot_head,
                    assigned if published else expected.snapshot_head)
                async with peer[0].conn.execute("SELECT operation_id FROM publication_operations WHERE operation_id LIKE 'marker-%'") as cursor:
                    self.assertEqual(len(await cursor.fetchall()), 3 if published else 0)
                with self.assertRaises(PublicationInfrastructureError):
                    views[0].require("one", model=type(sections[0]))
                if mode == "success":
                    before = tuple(trace)
                    self.assertEqual(await attempt(), result)
                    self.assertEqual(tuple(trace), before)
                    self.assertEqual(len(scopes), 1)

        for mode in ("success", "validate_refusal", "missing_base", "receipt_fault", "apply_refusal",
                     "rollback_unknown", "commit_unknown_applied", "commit_unknown_not_applied"):
            with self.subTest(mode=mode):
                run_async(check(mode))
