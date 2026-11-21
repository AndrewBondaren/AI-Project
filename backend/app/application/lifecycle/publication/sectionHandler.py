"""Lifecycle transaction participant; Snapshot owns the transaction barrier."""
from typing import Any, Protocol, cast
from pydantic import BaseModel
from app.application.lifecycle.storage.participantPort import (
    ILifecycleAcceptedChangesReader, ILifecycleParticipantReader, ILifecycleParticipantWriter,
)
from app.application.lifecycle.validation.stateValidator import LifecycleStateValidator, Native
from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.worldSnapshot.contracts.commitScope import IDomainCommitBinding
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext, SnapshotApplyContext
from app.dataModel.lifecycle.identity import LifecycleTransitionRef
from app.dataModel.lifecycle.results.applyIssue import LifecycleApplyIssue
from app.dataModel.lifecycle.storage.acceptedChanges import AcceptedChangesQuery
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.patch.results.sectionResult import SectionAccepted, SectionApplyReceipt, SectionRefused
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper


class ILifecycleEvidenceBinding[L: BaseModel, F: SectionRefused[LifecycleApplyIssue]](Protocol):
    def validate(self, section: L, context: SnapshotValidationContext) -> SectionAccepted | F: ...


class LifecycleSectionHandler[
    L: DomainSection[Any], Result: BaseModel, Capture: BaseModel, F: SectionRefused[LifecycleApplyIssue],
](DomainSectionHandler[L, LifecycleApplyIssue]):
    def __init__(self, *, contract: SectionContract[L], refusal_model: type[F],
                 accepted_reader: ILifecycleAcceptedChangesReader[Result],
                 current_reader: ILifecycleParticipantReader[L, Capture],
                 writer_binding: IDomainCommitBinding[ILifecycleParticipantWriter[L, F]],
                 evidence_binding: ILifecycleEvidenceBinding[L, F]) -> None:
        self._contract = contract
        self._refusal_model = refusal_model
        self._accepted_reader = accepted_reader
        self._current_reader = current_reader
        self._writer_binding = writer_binding
        self._evidence_binding = evidence_binding
        self._state_validator = LifecycleStateValidator(refusal_model)

    @property
    def contract(self) -> SectionContract[L]:
        return self._contract

    @property
    def refusal_model(self) -> type[F]:
        return self._refusal_model

    async def validate(self, section: L, context: SnapshotValidationContext) -> SectionAccepted | F:
        context.read_scope.assert_active()
        native = cast(Native, section)
        base = context.expected_world
        if base.active_timeline_id is None:
            raise ValueError("Lifecycle validation requires an active timeline")
        query = AcceptedChangesQuery(publication=base, refs=tuple(
            LifecycleTransitionRef(world_uid=base.world_uid, origin_timeline_id=base.active_timeline_id,
                                   change_uid=patch.prepared.transition.intent.change_uid)
            for patch in native.patches))
        evidence = self._evidence_binding.validate(section, context)
        accepted = await self._accepted_reader.lookup_accepted_changes(query, scope=context.read_scope)
        captures = await self._current_reader.read_for_section(section, publication=base, scope=context.read_scope)
        context.read_scope.assert_active()
        state = self._state_validator.validate(section, accepted=accepted, captures=captures, expected_world=base)
        errors = ValidatorAggregationHelper[LifecycleApplyIssue]((LifecycleApplyIssue,))
        for result in (evidence, state):
            if isinstance(result, SectionRefused):
                for issue in result.diagnostics:
                    errors.add(issue)
        issues = errors.snapshot()
        return (self._refusal_model(category=SnapshotApplyOutcomeKind.CONFLICT, diagnostics=issues)
                if issues else SectionAccepted())

    async def apply(self, section: L, context: SnapshotApplyContext) -> SectionApplyReceipt | F:
        context.scope.assert_active()
        evidence = self._evidence_binding.validate(section, context.validation)
        if isinstance(evidence, SectionRefused):
            return cast(F, evidence)
        appended = await self._writer_binding.bind(context.scope).append(
            section, expected=context.validation.expected_world, target=context.world_snapshot)
        context.scope.assert_active()
        if isinstance(appended, SectionRefused):
            return cast(F, appended)
        return SectionApplyReceipt(section_key=section.header.key,
            states=() if appended.state is None else (appended.state,),
            history=() if appended.history is None else (appended.history,), changed=appended.changed)
