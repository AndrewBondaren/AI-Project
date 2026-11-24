"""Synthetic subject behavior; payload semantics belong only to this mock."""
from typing import cast
from pydantic import BaseModel
from app.dataModel.lifecycle.evidence.effects import (
    LifecycleEffectKind,
)
from app.dataModel.lifecycle.operations.kind import LifecycleOperation
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.results.sectionResult import SectionAccepted
from app.dataModel.patch.changes.header import PatchHeader, PatchRef
from app.dataModel.patch.sections.section import SectionHeader
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from tests.lifecycle.support.domainSections import (
    TestDomainSectionA, TestDomainSectionB, TestDomainPatchA, TestDomainPatchB,
    MockMutationA, MockMutationB, MockSubjectIssue, MockSubjectCode,
    MockBatchA, MockBatchB, PrepareMockSubjectA, PrepareMockSubjectB,
    PreparedMockSubjectA, PreparedMockSubjectB,
)
from tests.lifecycle.support.mixedContracts import RefA, RefB, EffectA, EffectB, AdmissionA, AdmissionB
from tests.lifecycle.support.snapshotContracts import MockSubjectSectionRefused


def _effect(before: bool | None, after: bool) -> LifecycleEffectKind | None:
    if before is None and after is True:
        return LifecycleOperation.CREATE
    if before is True and after is False:
        return LifecycleOperation.END
    if before is False and after is True:
        return LifecycleOperation.REACTIVATE
    return None


def _analyze(section: TestDomainSectionA | TestDomainSectionB | PrepareMockSubjectA | PrepareMockSubjectB
             ) -> tuple[tuple[tuple[EffectA | EffectB, ...], ...], tuple[MockSubjectIssue, ...]]:
    errors = ValidatorAggregationHelper[MockSubjectIssue]((MockSubjectIssue,))
    if isinstance(section, (PrepareMockSubjectA, PrepareMockSubjectB)):
        batches_ref = FieldRef[PrepareMockSubjectA | PrepareMockSubjectB, tuple[MockBatchA | MockBatchB, ...]](
            lambda: type(section), lambda value: value.batches)
        patches = batches_ref.select(section)
        path = CheckedPath.root(type(section)).field(batches_ref)
    else:
        patches_ref = FieldRef[TestDomainSectionA | TestDomainSectionB, tuple[TestDomainPatchA | TestDomainPatchB, ...]](
            lambda: type(section), lambda value: value.patches)
        patches = patches_ref.select(section)
        path = CheckedPath.root(type(section)).field(patches_ref)
    batch_path = cast(CheckedPath[BaseModel, tuple[TestDomainPatchA | TestDomainPatchB | MockBatchA | MockBatchB, ...]], path)
    projections: list[tuple[EffectA | EffectB, ...]] = []
    slots: dict[tuple[RefA | RefB, str, LifecycleEffectKind], set[str]] = {}
    seen: set[tuple[RefA | RefB, str]] = set()
    actions: dict[RefA | RefB, str] = {}
    for index, patch in enumerate(patches):
        mutations_ref = FieldRef[TestDomainPatchA | TestDomainPatchB | MockBatchA | MockBatchB, tuple[MockMutationA | MockMutationB, ...]](
            lambda: type(patch), lambda value: value.mutations)
        mutation_path = batch_path.item(index).field(mutations_ref)
        projected: list[EffectA | EffectB] = []
        for ordinal, mutation in enumerate(mutations_ref.select(patch)):
            after_ref = FieldRef(lambda: type(mutation), lambda value: value.after)
            kind = _effect(mutation.before, after_ref.select(mutation))
            key = (mutation.entity, mutation.slot)
            invalid = kind is None or key in seen or (
                mutation.entity in actions and actions[mutation.entity] != mutation.action_uid)
            seen.add(key)
            actions.setdefault(mutation.entity, mutation.action_uid)
            if invalid:
                errors.add(MockSubjectIssue(code=MockSubjectCode.INVALID_MUTATION,
                    path=mutation_path.item(ordinal).field(after_ref).freeze(),
                    message="Invalid mutation, duplicate entity/slot or conflicting action"))
            if kind is None:
                continue
            effect = (EffectA(entity=mutation.entity, effect=kind, reason_action_uid=mutation.action_uid)
                      if isinstance(mutation.entity, RefA) else
                      EffectB(entity=mutation.entity, effect=kind, reason_action_uid=mutation.action_uid))
            if effect not in projected:
                projected.append(effect)
            slots.setdefault((mutation.entity, mutation.action_uid, kind), set()).add(mutation.slot)
        projections.append(tuple(projected))
        if isinstance(patch, (TestDomainPatchA, TestDomainPatchB)):
            native_model = type(patch)
            effects_ref = FieldRef[TestDomainPatchA | TestDomainPatchB, tuple[EffectA | EffectB, ...]](lambda: native_model, lambda value: value.effects)
            if tuple(projected) != effects_ref.select(patch):
                errors.add(MockSubjectIssue(code=MockSubjectCode.EFFECT_PAYLOAD_MISMATCH,
                    path=cast(CheckedPath[BaseModel, TestDomainPatchA | TestDomainPatchB], batch_path.item(index)).field(effects_ref).freeze(),
                    message="Native effects differ from the ordered payload projection"))
    if any(value != {"primary", "index"} for value in slots.values()):
        errors.add(MockSubjectIssue(code=MockSubjectCode.INCOMPLETE_EFFECT,
            path=path.freeze(), message="Each subject effect requires both primary and index mutations"))
    return tuple(projections), errors.snapshot()


def _verify(section: TestDomainSectionA | TestDomainSectionB) -> SectionAccepted | MockSubjectSectionRefused:
    _, issues = _analyze(section)
    return (MockSubjectSectionRefused(category=SnapshotApplyOutcomeKind.REJECTED, diagnostics=issues)
            if issues else SectionAccepted())


class MockSubjectPayloadVerifierA:
    def verify(self, section: TestDomainSectionA) -> SectionAccepted | MockSubjectSectionRefused:
        if type(section) is not TestDomainSectionA:
            raise TypeError("subject A verifier requires its exact native section")
        return _verify(TestDomainSectionA.model_validate(section, strict=True))


class MockSubjectPayloadVerifierB:
    def verify(self, section: TestDomainSectionB) -> SectionAccepted | MockSubjectSectionRefused:
        if type(section) is not TestDomainSectionB:
            raise TypeError("subject B verifier requires its exact native section")
        return _verify(TestDomainSectionB.model_validate(section, strict=True))


class MockSubjectProducerA:
    def prepare(self, request: PrepareMockSubjectA) -> PreparedMockSubjectA | MockSubjectSectionRefused:
        if type(request) is not PrepareMockSubjectA:
            raise TypeError("A producer requires exact PrepareMockSubjectA")
        request = PrepareMockSubjectA.model_validate(request, strict=True)
        projections, issues = _analyze(request)
        if issues:
            return MockSubjectSectionRefused(category=SnapshotApplyOutcomeKind.REJECTED, diagnostics=issues)
        effects = tuple(tuple(cast(EffectA, e) for e in projection) for projection in projections)
        section = TestDomainSectionA(header=SectionHeader(key=TestDomainSectionA.KEY,
            format_version=TestDomainSectionA.FORMAT_VERSION, depends_on=()), patches=tuple(
            TestDomainPatchA(header=PatchHeader(ref=PatchRef(operation_id=request.operation_id,
                section_key=TestDomainSectionA.KEY, ordinal=i), format_version=TestDomainSectionA.FORMAT_VERSION,
                depends_on=(), artifacts=()), base=request.publication, mutations=batch.mutations, effects=effect)
            for i, (batch, effect) in enumerate(zip(request.batches, effects, strict=True))))
        unique = tuple(dict.fromkeys(e for group in effects for e in group))
        return PreparedMockSubjectA(section=section, admissions=tuple(AdmissionA(publication=request.publication,
            action_uid=action, effects=tuple(e for e in unique if e.reason_action_uid == action))
            for action in dict.fromkeys(e.reason_action_uid for e in unique)))


class MockSubjectProducerB:
    def prepare(self, request: PrepareMockSubjectB) -> PreparedMockSubjectB | MockSubjectSectionRefused:
        if type(request) is not PrepareMockSubjectB:
            raise TypeError("B producer requires exact PrepareMockSubjectB")
        request = PrepareMockSubjectB.model_validate(request, strict=True)
        projections, issues = _analyze(request)
        if issues:
            return MockSubjectSectionRefused(category=SnapshotApplyOutcomeKind.REJECTED, diagnostics=issues)
        effects = tuple(tuple(cast(EffectB, e) for e in projection) for projection in projections)
        section = TestDomainSectionB(header=SectionHeader(key=TestDomainSectionB.KEY,
            format_version=TestDomainSectionB.FORMAT_VERSION, depends_on=()), patches=tuple(
            TestDomainPatchB(header=PatchHeader(ref=PatchRef(operation_id=request.operation_id,
                section_key=TestDomainSectionB.KEY, ordinal=i), format_version=TestDomainSectionB.FORMAT_VERSION,
                depends_on=(), artifacts=()), base=request.publication, mutations=batch.mutations, effects=effect)
            for i, (batch, effect) in enumerate(zip(request.batches, effects, strict=True))))
        unique = tuple(dict.fromkeys(e for group in effects for e in group))
        return PreparedMockSubjectB(section=section, admissions=tuple(AdmissionB(publication=request.publication,
            action_uid=action, effects=tuple(e for e in unique if e.reason_action_uid == action))
            for action in dict.fromkeys(e.reason_action_uid for e in unique)))
