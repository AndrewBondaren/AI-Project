"""Priority selection and immutable decision/fallback assembly."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

from app.application.policy.policyRead import PolicyReader, issue
from app.application.policy.policyStages import PolicyProblem, StageResult, selection_rules
from app.dataModel.placement.common import Specificity
from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyDecision import (
    ObjectAdmissionDecision, PolicyProvenance, PolicyReason, ValueSelectionDecision,
)
from app.dataModel.policy.policyEnums import (
    PolicyDisableReason, PolicyIssueReason, PolicyOperation, PolicyOrigin, PolicyState,
)
from app.dataModel.policy.policyFacts import KnownFact, UnknownFact, WaitingFact
from app.dataModel.policy.policyRules import DisableEffect, PolicyRule, RequireSupportEffect, SelectPriorityDefaultEffect
from app.dataModel.policy.policySpec import ObjectAdmissionPolicySpec, PolicySpec, ValueSelectionPolicySpec
from app.dataModel.validation.enums.resolutionMode import ResolutionMode

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


def rule_provenance(rule: PolicyRule[B, R]) -> PolicyProvenance:
    return PolicyProvenance(origin=PolicyOrigin.RULE, source_path=(), rule_id=rule.id)


@dataclass
class PolicyResolution(Generic[B, R]):
    spec: PolicySpec[B, R]
    mode: ResolutionMode
    priority: Specificity | None = None
    provenance: list[PolicyProvenance] = field(default_factory=list)
    reasons: list[PolicyReason[R]] = field(default_factory=list)

    def decision(self, state: PolicyState, *, behavior: B | None = None,
                 waiting: tuple[EntityUid, ...] = (), problems: tuple[PolicyProblem, ...] = ()
                 ) -> ObjectAdmissionDecision[B, R] | ValueSelectionDecision[B, R]:
        issues = tuple(dict.fromkeys(i for p in problems for i in p.issues))
        provenance = tuple(dict.fromkeys(self.provenance))
        if isinstance(self.spec, ObjectAdmissionPolicySpec):
            return ObjectAdmissionDecision[B, R](operation=PolicyOperation.OBJECT_ADMISSION,
                state=state, effective_priority=self.priority, behavior=behavior,
                reasons=tuple(self.reasons), waiting_supports=waiting, provenance=provenance, issues=issues)
        return ValueSelectionDecision[B, R](operation=PolicyOperation.VALUE_SELECTION,
            state=state, effective_priority=None, behavior=behavior,
            reasons=tuple(self.reasons), waiting_supports=waiting, provenance=provenance, issues=issues)

    def failure(self, problems: tuple[PolicyProblem, ...]) -> ObjectAdmissionDecision[B, R] | ValueSelectionDecision[B, R]:
        fallbacks = {f.reason: f for f in self.spec.fallback_rules}
        applicable = tuple(fallbacks.get(p.reason) for p in problems)
        if self.mode is ResolutionMode.RUNTIME and all(f is not None and f.disable_object for f in applicable):
            behaviors = {f.behavior for f in applicable if f is not None and f.behavior is not None}
            if len(behaviors) <= 1:
                self.reasons.append(PolicyReason[R](domain_reason=None, common_reason=PolicyDisableReason.ERROR_FALLBACK))
                self.provenance.extend(PolicyProvenance(origin=PolicyOrigin.FALLBACK,
                    source_path=(p.reason.value,), rule_id=None) for p in problems)
                return self.decision(PolicyState.DISABLED, behavior=next(iter(behaviors), None), problems=problems)
        return self.decision(PolicyState.UNRESOLVED, problems=problems)

    def stop(self, result: StageResult[B, R]) -> ObjectAdmissionDecision[B, R] | ValueSelectionDecision[B, R] | None:
        disables = tuple(r for r in result.matched if isinstance(r.effect, DisableEffect))
        if disables:
            for rule in disables:
                if isinstance(rule.effect, DisableEffect):
                    self.reasons.append(PolicyReason[R](domain_reason=rule.domain_reason, common_reason=rule.effect.reason))
                    self.provenance.append(rule_provenance(rule))
            behavior = self.spec.disabled_behavior if isinstance(self.spec, ValueSelectionPolicySpec) else None
            return self.decision(PolicyState.DISABLED, behavior=behavior)
        self.provenance.extend(rule_provenance(r) for r in result.matched if isinstance(r.effect, RequireSupportEffect))
        if result.disabled_supports:
            self.reasons.append(PolicyReason[R](domain_reason=None, common_reason=PolicyDisableReason.SUPPORT_DISABLED))
            self.provenance.extend(PolicyProvenance(origin=PolicyOrigin.RULE,
                source_path=("supports", uid), rule_id=r.id)
                for uid in result.disabled_supports for r in result.matched
                if isinstance(r.effect, RequireSupportEffect) and uid in r.effect.support_uids)
        if result.problems:
            return self.failure(result.problems)
        if result.disabled_supports:
            return self.decision(PolicyState.DISABLED)
        if result.waiting:
            return self.decision(PolicyState.WAITING_SUPPORT, waiting=result.waiting)
        return None

    def resolve_priority(self, spec: ObjectAdmissionPolicySpec[B, R], reader: PolicyReader,
                         defaults: StageResult[B, R]) -> ObjectAdmissionDecision[B, R] | ValueSelectionDecision[B, R] | None:
        authored = reader.read(spec.authored_priority_ref)
        ref = spec.authored_priority_ref
        origin = PolicyOrigin.AUTHORED
        if isinstance(authored, UnknownFact):
            return self.failure((PolicyProblem(PolicyIssueReason.UNKNOWN_FACT, (authored.issue,)),))
        if isinstance(authored, WaitingFact):
            raise ValueError("priority binding cannot be waiting")
        if authored.value is None:
            stopped = self.stop(defaults)
            if stopped is not None:
                return stopped
            choices = selection_rules(defaults)
            self.provenance.extend(rule_provenance(r) for r in choices)
            self.reasons.extend(PolicyReason[R](domain_reason=r.domain_reason,
                common_reason=PolicyDisableReason.DOMAIN_RULE) for r in choices if r.domain_reason is not None)
            refs = tuple(r.effect.ref for r in choices if isinstance(r.effect, SelectPriorityDefaultEffect))
            selected = tuple(reader.read(r) for r in refs)
            unknowns = tuple(v.issue for v in selected if isinstance(v, UnknownFact))
            if unknowns:
                return self.failure((PolicyProblem(PolicyIssueReason.UNKNOWN_FACT, unknowns),))
            if len({v.value for v in selected if isinstance(v, KnownFact)}) > 1:
                return self.failure((PolicyProblem(PolicyIssueReason.RULE_CONFLICT, tuple(
                    issue(PolicyIssueReason.RULE_CONFLICT, ("rules", r.id),
                          "equal-precedence priority values conflict") for r in choices)),))
            ref = refs[0] if refs else spec.domain_priority_ref
            origin = PolicyOrigin.DOMAIN_DEFAULT
        value = reader.read(ref)
        if isinstance(value, KnownFact) and value.value is None:
            ref = spec.terminal_priority_ref
            origin = PolicyOrigin.TERMINAL_DEFAULT
            value = reader.read(ref)
        if not isinstance(value, KnownFact) or type(value.value) is not int or value.value < 0:
            problem = value.issue if isinstance(value, UnknownFact) else issue(
                PolicyIssueReason.INVALID_INPUT, reader.path(ref), "priority must resolve to nonnegative integer")
            return self.failure((PolicyProblem(PolicyIssueReason.UNKNOWN_FACT if isinstance(value, UnknownFact)
                                              else PolicyIssueReason.INVALID_INPUT, (problem,)),))
        self.priority = value.value
        self.provenance.append(PolicyProvenance(origin=origin, source_path=reader.path(ref), rule_id=None))
        if self.priority == 0:
            self.reasons.append(PolicyReason[R](domain_reason=None, common_reason=PolicyDisableReason.ZERO_PRIORITY))
            return self.decision(PolicyState.DISABLED)
        return None
