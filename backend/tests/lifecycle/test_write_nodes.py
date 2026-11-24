"""Leaf contract tests; Snapshot target is a public-port spy, not a commit implementation."""
from unittest import TestCase
import asyncio

from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.patch.assembly.patchSetAssembler import PatchSetAssembler
from app.application.worldSnapshot.errors import SnapshotOperationCancelledError, SnapshotPublicError
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled, OperationCancellationReason
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyRelationIssue, SnapshotApplyCode
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.errors.publicFault import (
    SnapshotPublicFailureKind, SnapshotPublicFault, SnapshotPublicOperation,
)
from tests.lifecycle.support.assemblePatchSetNode import AssemblePatchSetNode
from tests.lifecycle.support.applySnapshotNode import ApplySnapshotNode
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockPatchSet, MockSnapshotApplyResult
from tests.lifecycle.support.writeNodeBindings import (
    APPLY_SNAPSHOT_CONTRACT, ASSEMBLE_PATCH_SET_CONTRACT, register_mock_write_leaves,
)
from tests.lifecycle.support.writeNodeContracts import MockApplySnapshotInput, MockAssemblePatchSetInput
from tests.lifecycle.test_snapshot_validation import scenario


def run_immediate(coro):
    try:
        coro.send(None)
    except StopIteration as done:
        return done.value
    raise AssertionError("leaf spy unexpectedly suspended")


class ApplySpy:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0
        self.received = None

    async def apply(self, patch_set):
        self.calls += 1
        self.received = patch_set
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class WriteLeafTests(TestCase):
    def test_apply_business_outcomes_remain_output_values(self):
        _, patch_set, *_ = scenario()
        issue = SnapshotApplyRelationIssue(code=SnapshotApplyCode.DEPENDENCY_MISMATCH,
            section_key="mock.lifecycle", player_uid=None, artifact=None)
        for category in (SnapshotApplyOutcomeKind.CONFLICT, SnapshotApplyOutcomeKind.REJECTED):
            with self.subTest(category=category):
                result = MockSnapshotApplyResult(category=category,
                    operation_id=patch_set.operation_id, request_fingerprint=patch_set.preparation_fingerprint,
                    committed=None, diagnostics=(issue,))
                spy = ApplySpy(result)
                output = run_immediate(ApplySnapshotNode(snapshot=spy).execute(
                    MockApplySnapshotInput(patch_set=patch_set)))
                self.assertIs(type(output.value), MockSnapshotApplyResult)
                self.assertEqual(output.value, result)
                self.assertEqual(spy.calls, 1)

    def test_assembly_success_and_refusal_do_not_call_apply(self):
        _, patch_set, *_ = scenario()
        assembler = PatchSetAssembler(MockAssemblyInput, MockPatchSet)
        apply_spy = ApplySpy(None)
        node = AssemblePatchSetNode(assembler=assembler)
        request = MockAssemblyInput(**patch_set.model_dump())
        success = run_immediate(node.execute(MockAssemblePatchSetInput(request=request)))
        self.assertIs(type(success.value), MockPatchSet)
        self.assertEqual(success.value, patch_set)
        duplicate = MockAssemblyInput(**{**patch_set.model_dump(), "sections": patch_set.sections * 2})
        refusal = run_immediate(node.execute(MockAssemblePatchSetInput(request=duplicate)))
        self.assertIs(type(refusal.value), PatchSetAssemblyRefused)
        self.assertTrue(refusal.value.diagnostics)
        self.assertEqual(apply_spy.calls, 0)

    def test_apply_public_error_and_durable_cancel_are_distinct(self):
        _, patch_set, *_ = scenario()
        fault = SnapshotPublicFault(operation=SnapshotPublicOperation.APPLY,
            kind=SnapshotPublicFailureKind.BUSY, operation_id=patch_set.operation_id,
            request_fingerprint=patch_set.preparation_fingerprint, input_issues=())
        cancelled = OperationCancelled(operation_id=patch_set.operation_id,
            reason=OperationCancellationReason.REQUESTED)
        for exception, expected in ((SnapshotPublicError(fault), "fault"),
                                    (SnapshotOperationCancelledError(cancelled), "outcome")):
            with self.subTest(expected=expected):
                spy = ApplySpy(exception)
                with self.assertRaises(PythonNodeError) as raised:
                    run_immediate(ApplySnapshotNode(snapshot=spy).execute(MockApplySnapshotInput(patch_set=patch_set)))
                self.assertEqual(getattr(raised.exception.error, expected),
                                 fault if expected == "fault" else cancelled)
                self.assertEqual(spy.calls, 1)
                self.assertIs(type(spy.received), MockPatchSet)
                self.assertEqual(spy.received, patch_set)
        spy = ApplySpy(asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            run_immediate(ApplySnapshotNode(snapshot=spy).execute(MockApplySnapshotInput(patch_set=patch_set)))

    def test_contract_registration(self):
        registry = NodeRegistry()
        register_mock_write_leaves(registry)
        self.assertIs(registry.get(AssemblePatchSetNode.id, ASSEMBLE_PATCH_SET_CONTRACT).contract,
                      ASSEMBLE_PATCH_SET_CONTRACT)
        self.assertIs(registry.get(ApplySnapshotNode.id, APPLY_SNAPSHOT_CONTRACT).contract,
                      APPLY_SNAPSHOT_CONTRACT)
        with self.assertRaises(ValueError):
            register_mock_write_leaves(registry)
