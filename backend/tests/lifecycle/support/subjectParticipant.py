"""Synthetic source owner: validates payload and accepted before-state."""
from typing import overload
from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext, SnapshotApplyContext
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionApplyReceipt
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.sections.refs import SectionStateRef, SectionHistoryRef
from app.dataModel.worldSnapshot.sections.retention import SectionStateRetention, SectionHistoryRetention
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from tests.lifecycle.support.domainSections import (
    TestDomainSectionA, TestDomainSectionB, TestDomainPatchA, TestDomainPatchB,
    MockMutationA, MockMutationB, MockSubjectCode, MockSubjectIssue,
    MockSubjectObservationA, MockSubjectObservationB, MockSubjectCaptureA, MockSubjectCaptureB,
)
from tests.lifecycle.support.mixedContracts import RefA, RefB
from tests.lifecycle.support.snapshotContracts import MockSubjectSectionRefused
from tests.lifecycle.support.subjectMock import MockSubjectPayloadVerifierA, MockSubjectPayloadVerifierB


class MockSubjectParticipant:
    def __init__(self, *, scope: CommitScope, publication: WorldPublicationRef,
                 observations: tuple[MockSubjectObservationA | MockSubjectObservationB, ...] = ()) -> None:
        self.scope = scope
        self.publication = publication
        self._values: dict[tuple[RefA | RefB, str], bool | None] = {
            (item.entity, item.slot): item.value for item in observations}
        if len(self._values) != len(observations):
            raise ValueError("duplicate initial subject observation")

    @overload
    async def read_for_section(self, section: TestDomainSectionA, *, publication: WorldPublicationRef, scope: CommitReadScope) -> MockSubjectCaptureA: ...
    @overload
    async def read_for_section(self, section: TestDomainSectionB, *, publication: WorldPublicationRef, scope: CommitReadScope) -> MockSubjectCaptureB: ...
    async def read_for_section(self, section: TestDomainSectionA | TestDomainSectionB, *,
                               publication: WorldPublicationRef, scope: CommitReadScope) -> MockSubjectCaptureA | MockSubjectCaptureB:
        scope.assert_active()
        if scope is not self.scope.read_scope or publication != self.publication:
            raise ValueError("subject read is bound to another scope/publication")
        if isinstance(section, TestDomainSectionA):
            return MockSubjectCaptureA(publication=self.publication, observations=tuple(
                MockSubjectObservationA(entity=mutation.entity, slot=mutation.slot,
                    value=self._values.get((mutation.entity, mutation.slot)))
                for patch in section.patches for mutation in patch.mutations))
        return MockSubjectCaptureB(publication=self.publication, observations=tuple(
            MockSubjectObservationB(entity=mutation.entity, slot=mutation.slot,
                value=self._values.get((mutation.entity, mutation.slot)))
            for patch in section.patches for mutation in patch.mutations))

    async def validate(self, section: TestDomainSectionA | TestDomainSectionB, context: SnapshotValidationContext) -> SectionAccepted | MockSubjectSectionRefused:
        semantic = (MockSubjectPayloadVerifierA().verify(section) if isinstance(section, TestDomainSectionA)
                    else MockSubjectPayloadVerifierB().verify(section))
        if isinstance(semantic, MockSubjectSectionRefused):
            return semantic
        capture = await self.read_for_section(section, publication=context.expected_world, scope=context.read_scope)
        observations = {(item.entity, item.slot): item.value for item in capture.observations}
        patches_ref = FieldRef[TestDomainSectionA | TestDomainSectionB, tuple[TestDomainPatchA | TestDomainPatchB, ...]](
            lambda: type(section), lambda value: value.patches)
        path = CheckedPath.root(type(section)).field(patches_ref)
        errors = ValidatorAggregationHelper[MockSubjectIssue]((MockSubjectIssue,))
        for i, patch in enumerate(patches_ref.select(section)):
            if patch.base != context.expected_world or patch.header.ref.operation_id != context.operation_id:
                raise ValueError("subject native base/operation differs from admitted context")
            mutations_ref = FieldRef[TestDomainPatchA | TestDomainPatchB, tuple[MockMutationA | MockMutationB, ...]](
                lambda: type(patch), lambda value: value.mutations)
            for j, mutation in enumerate(mutations_ref.select(patch)):
                before_ref = FieldRef(lambda: type(mutation), lambda value: value.before)
                if observations[(mutation.entity, mutation.slot)] != before_ref.select(mutation):
                    errors.add(MockSubjectIssue(code=MockSubjectCode.SUBJECT_BEFORE_MISMATCH,
                        path=path.item(i).field(mutations_ref).item(j).field(before_ref).freeze(),
                        message="Subject before-value differs from the accepted publication"))
        issues = errors.snapshot()
        return (MockSubjectSectionRefused(category=SnapshotApplyOutcomeKind.CONFLICT, diagnostics=issues)
                if issues else SectionAccepted())

    async def apply(self, section: TestDomainSectionA | TestDomainSectionB, context: SnapshotApplyContext) -> SectionApplyReceipt | MockSubjectSectionRefused:
        context.scope.assert_active()
        if context.scope is not self.scope:
            raise ValueError("subject writer belongs to another transaction")
        validation = await self.validate(section, context.validation)
        if isinstance(validation, MockSubjectSectionRefused):
            return validation
        values = dict(self._values)
        for patch in section.patches:
            for mutation in patch.mutations:
                values[(mutation.entity, mutation.slot)] = mutation.after
        result = SectionApplyReceipt(section_key=section.header.key,
            states=(SectionStateRetention(state=SectionStateRef(snapshot=context.world_snapshot,
                section_key=section.header.key, format_version=section.header.format_version), artifacts=()),),
            history=(SectionHistoryRetention(history=SectionHistoryRef(snapshot=context.world_snapshot,
                section_key=section.header.key, format_version=section.header.format_version), artifacts=()),),
            changed=tuple(patch.header.ref for patch in section.patches))
        context.scope.assert_active()
        self._values = values
        return result


class _MockSubjectHandler[S: (TestDomainSectionA, TestDomainSectionB)](DomainSectionHandler[S, MockSubjectIssue]):
    def __init__(self, contract: SectionContract[S], participant: MockSubjectParticipant) -> None:
        self._contract = contract
        self._participant = participant

    @property
    def contract(self) -> SectionContract[S]:
        return self._contract

    @property
    def refusal_model(self) -> type[MockSubjectSectionRefused]:
        return MockSubjectSectionRefused

    async def validate(self, section: S, context: SnapshotValidationContext) -> SectionAccepted | MockSubjectSectionRefused:
        return await self._participant.validate(section, context)

    async def apply(self, section: S, context: SnapshotApplyContext) -> SectionApplyReceipt | MockSubjectSectionRefused:
        return await self._participant.apply(section, context)


class MockSubjectHandlerA(_MockSubjectHandler[TestDomainSectionA]):
    pass


class MockSubjectHandlerB(_MockSubjectHandler[TestDomainSectionB]):
    pass
