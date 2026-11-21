"""Real Snapshot validation phase with Lifecycle and subject participants.

This tests the shared validation barrier, not durable publication/rollback.
"""
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from types import SimpleNamespace
from app.application.patch.contracts.sectionHandler import SectionContract
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.patch.encoding.sectionFingerprint import SectionFingerprint
from app.application.lifecycle.publication.sectionHandler import LifecycleSectionHandler
from app.application.lifecycle.publication.sectionCodec import LifecycleSectionCodec
from app.application.lifecycle.publication.sectionPipelineOpenPipeline import LifecycleSectionPipelineOpenPipeline
from app.application.publication.contracts.resultBinding import PublicationResultBinding
from app.application.worldSnapshot.service.worldSnapshotService import WorldSnapshotService, _SnapshotValidationRefused
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext
from app.dataModel.worldSnapshot.identity.refs import WorldSnapshotRef
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from tests.lifecycle import test_section as sections
from tests.lifecycle.test_apply_predicates import subject_section
from tests.lifecycle.test_participant import MockCommitScope
from tests.lifecycle.support import mixedContracts as m, domainSections as d
from tests.lifecycle.support.subjectCodec import MockSubjectCodec
from tests.lifecycle.support.subjectParticipant import MockSubjectParticipant, MockSubjectHandlerA
from tests.lifecycle.support.lifecycleParticipant import MockLifecycleParticipant
from tests.lifecycle.support.evidenceBinding import MockLifecycleEvidenceBinding
from tests.lifecycle.support.manifest import MOCK_NATIVE_MANIFEST
from tests.lifecycle.support.snapshotManifest import MOCK_SNAPSHOT_MANIFEST
from tests.lifecycle.support.snapshotContracts import (
    MockSectionRefused, MockLifecycleSectionRefused, MockSnapshotApplyResult, MockPatchSet,
)


def scenario(*, retry=False, false_effect=False, lifecycle_first=False, guard_apply=True):
    scope = MockCommitScope()
    pairs = [sections.prepared_and_coverage(LifecycleOperation.CREATE, "A", i) for i in range(2)]
    source = subject_section()
    effects = tuple(coverage[0].effect for _, coverage in pairs)
    patches = tuple(patch.model_copy(update={
        "effects": effects,
        "mutations": tuple(mutation.model_copy(update={"entity": effect.entity, **({"before": True, "after": False} if false_effect else {})})
                           for mutation, effect in zip(patch.mutations, effects, strict=True))
    }) for patch in source.patches)
    source = source.model_copy(update={"patches": patches})
    base = patches[0].base
    subject = MockSubjectParticipant(scope=scope, publication=base, observations=tuple(
        d.MockSubjectObservationA(entity=mutation.entity, slot=mutation.slot, value=True)
        for patch in patches for mutation in patch.mutations) if retry else ())
    subject_contract = SectionContract(key=source.header.key, section_model=d.TestDomainSectionA,
        supported_versions=frozenset({1}), manifest=MOCK_NATIVE_MANIFEST)
    subject_handler = MockSubjectHandlerA(subject_contract, subject)
    registry = SectionRegistry(MockSectionRefused)
    registry.register(subject_contract, subject_handler, MockSubjectCodec(subject_contract))
    fingerprint = SectionFingerprint(registry).fingerprint(source)
    refs = tuple(p.header.ref for p in patches)
    evidence = tuple(coverage[0].model_copy(update={"patch_refs": refs,
        "section": coverage[0].section.model_copy(update={"section_fingerprint": fingerprint})})
        for _, coverage in pairs)
    request = m.PrepareLifecycleSectionAB(operation_id="publish", expected_world=base,
        changes=tuple(prepared for prepared, _ in pairs), domain_evidence=evidence)
    binding = sections.section_binding()
    native = LifecycleSectionPipelineOpenPipeline(binding=binding).prepare_section(request)
    participant = MockLifecycleParticipant(scope=scope, publication=base,
        states=tuple(p.after for patch in native.patches for p in patch.prepared.transition.participants) if retry else (),
        transitions=tuple(p.prepared.transition for p in native.patches) if retry else ())
    lifecycle_handler = LifecycleSectionHandler(contract=binding.section_contract,
        refusal_model=MockLifecycleSectionRefused, accepted_reader=participant, current_reader=participant,
        writer_binding=participant, evidence_binding=MockLifecycleEvidenceBinding())
    registry.register(binding.section_contract, lifecycle_handler, LifecycleSectionCodec(binding.section_contract))
    patch_set = MockPatchSet(format_version=1, operation_id="publish", preparation_fingerprint="c" * 64,
        world_uid=base.world_uid, timeline_id=base.active_timeline_id, turn_id=1, expected_world=base, expected_players=(),
        sections=(native, source) if lifecycle_first else (source, native))
    publication = PublicationResultBinding(result_model=MockSnapshotApplyResult, snapshot_format_version=1,
        record_model=OperationRecord[MockSnapshotApplyResult], manifest=MOCK_SNAPSHOT_MANIFEST,
        limits=DecodeLimits(max_bytes=1000000, max_nodes=100000, max_depth=100, max_items=10000))
    service = WorldSnapshotService(registry, None, None, None, publication_binding=publication,
        operations=SimpleNamespace(result_binding=publication, record_model=publication.record_model))
    if guard_apply:
        subject_handler.apply = AsyncMock(side_effect=AssertionError("apply during validation"))
        lifecycle_handler.apply = AsyncMock(side_effect=AssertionError("apply during validation"))
    return service, patch_set, scope, native, subject_handler, lifecycle_handler


class SnapshotValidationTests(IsolatedAsyncioTestCase):
    async def test_handler_apply_maps_assigned_refs_and_noop_receipt(self):
        service, request, scope, native, subject, lifecycle = scenario(guard_apply=False)
        validation = await service._validate_sections(request, scope=scope.read_scope,
                                                      resolved_dependencies=native.header.depends_on)
        target = WorldSnapshotRef(world_uid=request.world_uid, timeline_id=request.timeline_id, snapshot_id="assigned")
        next_publication = request.expected_world.model_copy(update={"publication_id": "assigned-publication", "snapshot_head": target})
        context = SnapshotApplyContext(validation=validation, world_snapshot=target, player_snapshots=(),
                                       scope=scope, next_publication=next_publication)
        subject_receipt = await subject.apply(request.sections[0], context)
        self.assertEqual(subject_receipt.changed, tuple(p.header.ref for p in request.sections[0].patches))
        receipt = await lifecycle.apply(native, context)
        self.assertEqual(receipt.changed, tuple(p.header.ref for p in native.patches))
        self.assertEqual(receipt.states[0].state.snapshot, target)
        self.assertEqual(receipt.history[0].history.snapshot, target)
        repeated = await lifecycle.apply(native, context)
        self.assertEqual((repeated.changed, repeated.states, repeated.history), ((), (), ()))

    async def test_valid_shared_validation_and_exact_admitted_view(self):
        service, request, scope, native, subject, lifecycle = scenario()
        context = await service._validate_sections(request, scope=scope.read_scope, resolved_dependencies=native.header.depends_on)
        admitted_native = next(section for section in request.sections if type(section) is m.LifecycleSectionAB)
        self.assertIs(context.admitted_sections.require("mock.lifecycle", model=m.LifecycleSectionAB), admitted_native)
        subject.apply.assert_not_awaited()
        lifecycle.apply.assert_not_awaited()
        scope.read_scope.active = False
        with self.assertRaises(RuntimeError):
            context.admitted_sections.require("mock.lifecycle", model=m.LifecycleSectionAB)

    async def test_equal_lifecycle_retry_does_not_suppress_subject_refusal_in_either_order(self):
        for first in (False, True):
            service, request, scope, native, subject, lifecycle = scenario(retry=True, lifecycle_first=first)
            with self.assertRaises(_SnapshotValidationRefused) as raised:
                await service._validate_sections(request, scope=scope.read_scope, resolved_dependencies=native.header.depends_on)
            self.assertEqual(raised.exception.category, SnapshotApplyOutcomeKind.CONFLICT)
            self.assertTrue(all(issue.code is d.MockSubjectCode.SUBJECT_BEFORE_MISMATCH for issue in raised.exception.diagnostics))
            subject.apply.assert_not_awaited()
            lifecycle.apply.assert_not_awaited()

    async def test_valid_fingerprint_does_not_prove_subject_payload_effect(self):
        service, request, scope, native, subject, lifecycle = scenario(false_effect=True)
        with self.assertRaises(_SnapshotValidationRefused) as raised:
            await service._validate_sections(request, scope=scope.read_scope, resolved_dependencies=native.header.depends_on)
        self.assertEqual(raised.exception.category, SnapshotApplyOutcomeKind.REJECTED)
        self.assertTrue(all(issue.code is d.MockSubjectCode.EFFECT_PAYLOAD_MISMATCH for issue in raised.exception.diagnostics))
        subject.apply.assert_not_awaited()
        lifecycle.apply.assert_not_awaited()

    async def test_fingerprint_substitution_is_rejected_by_shared_dependency_phase(self):
        service, request, scope, native, subject, lifecycle = scenario()
        dependency = native.header.depends_on[0].model_copy(update={"section_fingerprint": "f" * 64})
        native = native.model_copy(update={
            "header": native.header.model_copy(update={"depends_on": (dependency,)}),
            "domain_evidence": tuple(e.model_copy(update={"section": dependency}) for e in native.domain_evidence)})
        request = request.model_copy(update={"sections": (request.sections[0], native)})
        subject.validate = AsyncMock(side_effect=AssertionError("handler ran before dependency binding"))
        lifecycle.validate = AsyncMock(side_effect=AssertionError("handler ran before dependency binding"))
        with self.assertRaises(_SnapshotValidationRefused):
            await service._validate_sections(request, scope=scope.read_scope, resolved_dependencies=(dependency,))
        subject.validate.assert_not_awaited()
        lifecycle.validate.assert_not_awaited()
