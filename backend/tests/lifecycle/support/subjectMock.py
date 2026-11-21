"""Synthetic subject behavior; payload semantics belong only to this mock."""
from typing import Literal
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.results.sectionResult import SectionAccepted
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from tests.lifecycle.support.domainSections import (
    TestDomainSectionA, TestDomainSectionB, TestDomainPatchA, TestDomainPatchB,
    MockMutationA, MockMutationB, MockSubjectIssue, MockSubjectCode,
)
from tests.lifecycle.support.mixedContracts import RefA, RefB, EffectA, EffectB
from tests.lifecycle.support.snapshotContracts import MockSubjectSectionRefused


def _effect(before: bool | None, after: bool) -> Literal["create", "end", "reactivate"] | None:
    if before is None and after is True:
        return "create"
    if before is True and after is False:
        return "end"
    if before is False and after is True:
        return "reactivate"
    return None


def _verify(section: TestDomainSectionA | TestDomainSectionB) -> SectionAccepted | MockSubjectSectionRefused:
    errors = ValidatorAggregationHelper[MockSubjectIssue]((MockSubjectIssue,))
    patches_ref = FieldRef[TestDomainSectionA | TestDomainSectionB, tuple[TestDomainPatchA | TestDomainPatchB, ...]](
        lambda: type(section), lambda value: value.patches)
    patches = patches_ref.select(section)
    path = CheckedPath.root(type(section)).field(patches_ref)
    slots: dict[tuple[RefA | RefB, str, str], set[str]] = {}
    seen: set[tuple[RefA | RefB, str]] = set()
    actions: dict[RefA | RefB, str] = {}
    for index, patch in enumerate(patches):
        mutations_ref = FieldRef[TestDomainPatchA | TestDomainPatchB, tuple[MockMutationA | MockMutationB, ...]](
            lambda: type(patch), lambda value: value.mutations)
        effects_ref = FieldRef(lambda: type(patch), lambda value: value.effects)
        mutation_path = path.item(index).field(mutations_ref)
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
        if tuple(projected) != effects_ref.select(patch):
            errors.add(MockSubjectIssue(code=MockSubjectCode.EFFECT_PAYLOAD_MISMATCH,
                path=path.item(index).field(effects_ref).freeze(),
                message="Native effects differ from the ordered payload projection"))
    if any(value != {"primary", "index"} for value in slots.values()):
        errors.add(MockSubjectIssue(code=MockSubjectCode.INCOMPLETE_EFFECT,
            path=path.freeze(), message="Each subject effect requires both primary and index mutations"))
    issues = errors.snapshot()
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
