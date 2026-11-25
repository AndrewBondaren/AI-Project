"""Synchronous driving of await-free CALL methods avoids Windows loop setup."""

import unittest

from app.application.engine.contracts.invocation.resumeEvent import CallCancelled, CallFailure, CallResults, CallSuccess, ReturnedCall
from app.application.engine.registration.nodeRegistry import NodeRegistry
from app.application.engine.runtime.execution.pythonNodeError import PythonNodeError
from app.application.patch.assembly.patchSetAssembler import PatchSetAssembler
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled, OperationCancellationReason
from app.dataModel.patch.results.assembly import PatchSetAssemblyRefused
from app.dataModel.worldSnapshot.errors.publicFault import SnapshotPublicFault, SnapshotPublicFailureKind, SnapshotPublicOperation
from tests.lifecycle.support.mixedContracts import PrepareLifecycleSectionAB
from tests.lifecycle.support.nodeContracts import SectionNodeOutputAB
from tests.lifecycle.support.nodes.writeChanges.prepareChangesNode import PrepareChangesNode, SECTION_KEY, SECTION_TARGET
from tests.lifecycle.support.nodes.writeChanges.writeChangesNode import WriteChangesNode, PREPARE_KEY, PREPARE_TARGET, ASSEMBLE_KEY, ASSEMBLE_TARGET, APPLY_KEY, APPLY_TARGET
from tests.lifecycle.support.nodes.writeChanges.registration import register_mock_write_orchestrators
from tests.lifecycle.support.writeChangesContracts import MockAssemblyContext, MockPrepareChangesInput, MockWriteChangesInput, MockWriteChangesState
from tests.lifecycle.support.writeNodeContracts import MockAssemblePatchSetOutput, SnapshotPublicNodeError, SnapshotOperationCancelledNodeError
from tests.lifecycle.support.snapshotContracts import MockAssemblyInput, MockPatchSet
from tests.lifecycle.test_snapshot_validation import scenario


def drive(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    raise AssertionError("unexpected suspension")


def returned(key, target, result):
    return CallResults((ReturnedCall(key, target, result),))


class WriteChangesOrchestratorTests(unittest.TestCase):
    def setUp(self):
        _, self.patch_set, _, self.native, _, _ = scenario()
        request = PrepareLifecycleSectionAB(
            operation_id=self.patch_set.operation_id, expected_world=self.patch_set.expected_world,
            changes=tuple(p.prepared for p in self.native.patches), domain_evidence=self.native.domain_evidence,
        )
        self.preparation = MockPrepareChangesInput(
            section_request=request, subject_section=self.patch_set.sections[0],
            assembly_context=MockAssemblyContext(**self.patch_set.model_dump(exclude={"sections"})),
        )

    def test_success_trace_to_apply(self):
        prepare = PrepareChangesNode()
        section = drive(prepare.start(self.preparation))
        self.assertEqual(section.target, SECTION_TARGET)
        prepared = drive(prepare.resume(section.state, returned(
            SECTION_KEY, SECTION_TARGET, CallSuccess(SectionNodeOutputAB(value=self.native)),
        )))
        self.assertEqual(prepared.output.value.sections, self.patch_set.sections)
        self.assertEqual(prepared.output.value.preparation_fingerprint, self.patch_set.preparation_fingerprint)
        write = WriteChangesNode()
        first = drive(write.start(MockWriteChangesInput(preparation=self.preparation)))
        self.assertEqual(first.target, PREPARE_TARGET)
        second = drive(write.resume(first.state, returned(PREPARE_KEY, PREPARE_TARGET, CallSuccess(prepared.output))))
        self.assertEqual(second.target, ASSEMBLE_TARGET)
        self.assertEqual(second.input.request.sections, self.patch_set.sections)
        third = drive(write.resume(second.state, returned(
            ASSEMBLE_KEY, ASSEMBLE_TARGET, CallSuccess(MockAssemblePatchSetOutput(value=self.patch_set)),
        )))
        self.assertEqual(third.target, APPLY_TARGET)
        self.assertEqual(third.input.patch_set, self.patch_set)
        self.assertEqual((section.key, first.key, second.key, third.key),
                         (SECTION_KEY, PREPARE_KEY, ASSEMBLE_KEY, APPLY_KEY))

    def test_cancel_stops_dependent_call(self):
        write = WriteChangesNode()
        first = drive(write.start(MockWriteChangesInput(preparation=self.preparation)))
        with self.assertRaises(BaseException) as caught:
            drive(write.resume(first.state, returned(PREPARE_KEY, PREPARE_TARGET, CallCancelled())))
        self.assertEqual(type(caught.exception).__name__, "CancelledError")

    def test_apply_typed_errors_preserve_owning_payload(self):
        write = WriteChangesNode()
        state = MockWriteChangesState(stage="apply", request=MockWriteChangesInput(preparation=self.preparation))
        fault = SnapshotPublicFault(operation=SnapshotPublicOperation.APPLY,
            kind=SnapshotPublicFailureKind.BUSY, operation_id=self.patch_set.operation_id,
            request_fingerprint=self.patch_set.preparation_fingerprint, input_issues=())
        cancelled = OperationCancelled(operation_id=self.patch_set.operation_id,
            reason=OperationCancellationReason.REQUESTED)
        for error, field, payload in (
            (SnapshotPublicNodeError(fault=fault), "fault", fault),
            (SnapshotOperationCancelledNodeError(outcome=cancelled), "outcome", cancelled),
        ):
            with self.subTest(field=field), self.assertRaises(PythonNodeError) as caught:
                drive(write.resume(state, returned(APPLY_KEY, APPLY_TARGET, CallFailure(error))))
            self.assertEqual(getattr(caught.exception.error, field), payload)

    def test_assembly_refusal_stops_apply(self):
        duplicate = MockAssemblyInput(**{
            **self.patch_set.model_dump(), "sections": self.patch_set.sections * 2,
        })
        refusal = PatchSetAssembler(MockAssemblyInput, MockPatchSet).assemble(duplicate)
        self.assertIs(type(refusal), PatchSetAssemblyRefused)
        write = WriteChangesNode()
        state = MockWriteChangesState(stage="assemble", request=MockWriteChangesInput(preparation=self.preparation))
        result = drive(write.resume(state, returned(
            ASSEMBLE_KEY, ASSEMBLE_TARGET, CallSuccess(MockAssemblePatchSetOutput(value=refusal)),
        )))
        self.assertEqual(result.output.value, refusal)

    def test_registration_has_unique_ids(self):
        registry = NodeRegistry()
        register_mock_write_orchestrators(registry)
        self.assertEqual(len(registry.ids()), len(set(registry.ids())))
        with self.assertRaises(ValueError):
            register_mock_write_orchestrators(registry)
