"""One staged policy executor. Scheduling, geometry and reporting belong to callers."""

from enum import Enum
from typing import TypeVar, overload

from app.application.policy.policyRead import PolicyReader, issue
from app.application.policy.policyResolution import PolicyResolution, rule_provenance
from app.application.policy.policyStages import PolicyProblem, evaluate_stage, selection_rules
from app.dataModel.policy.objectAdmissionPolicyDefinition import ObjectAdmissionFacts
from app.dataModel.policy.policyBindings import PolicyFacts, PolicyInputs
from app.dataModel.policy.policyDecision import ObjectAdmissionDecision, PolicyReason, ValueSelectionDecision
from app.dataModel.policy.policyEnums import PolicyDisableReason, PolicyIssueReason, PolicyOperation, PolicyStage, PolicyState
from app.dataModel.policy.policyFacts import KnownFact
from app.dataModel.policy.policyRules import DisableEffect, SelectBehaviorEffect, SelectPriorityDefaultEffect
from app.dataModel.policy.policySpec import ObjectAdmissionPolicySpec, PolicySpec, ValueSelectionPolicySpec
from app.dataModel.validation.enums.resolutionMode import ResolutionMode

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


class PolicyResolver:
    @overload
    def resolve(self, spec: ObjectAdmissionPolicySpec[B, R], sources: PolicyInputs, facts: PolicyFacts, *,
                mode: ResolutionMode, resume: ObjectAdmissionDecision[B, R] | None = None) -> ObjectAdmissionDecision[B, R]: ...

    @overload
    def resolve(self, spec: ValueSelectionPolicySpec[B, R], sources: PolicyInputs, facts: PolicyFacts, *,
                mode: ResolutionMode) -> ValueSelectionDecision[B, R]: ...

    def resolve(self, spec: PolicySpec[B, R], sources: PolicyInputs, facts: PolicyFacts, *,
                mode: ResolutionMode, resume: ObjectAdmissionDecision[B, R] | None = None
                ) -> ObjectAdmissionDecision[B, R] | ValueSelectionDecision[B, R]:
        if not isinstance(mode, ResolutionMode):
            raise ValueError("policy resolution requires ResolutionMode")
        if resume is not None:
            type(resume).model_validate(resume, strict=True)
        if resume is not None and (not isinstance(spec, ObjectAdmissionPolicySpec)
                or resume.operation is not PolicyOperation.OBJECT_ADMISSION
                or resume.state is not PolicyState.WAITING_SUPPORT
                or resume.effective_priority is None or resume.effective_priority <= 0):
            raise ValueError("resume requires a positive waiting object decision from the caller binding")
        reader = PolicyReader(sources, facts)
        result = PolicyResolution[B, R](spec, mode)
        errors = reader.validate()
        if errors:
            return result.failure((PolicyProblem(PolicyIssueReason.INVALID_INPUT, errors),))
        if resume is None:
            stopped = result.stop(evaluate_stage(spec.rules, PolicyStage.ABSOLUTE_GATE, reader))
            if stopped is not None:
                return stopped
            if isinstance(spec, ObjectAdmissionPolicySpec):
                priority_gates = evaluate_stage(tuple(r for r in spec.rules
                    if isinstance(r.effect, DisableEffect)), PolicyStage.PRIORITY, reader)
                if any(isinstance(r.effect, DisableEffect) for r in priority_gates.matched):
                    stopped = result.stop(priority_gates)
                    if stopped is not None:
                        return stopped
                defaults = evaluate_stage(tuple(r for r in spec.rules if isinstance(r.effect, SelectPriorityDefaultEffect)),
                                          PolicyStage.PRIORITY, reader)
                stopped = result.resolve_priority(spec, reader, defaults)
                if stopped is not None:
                    return stopped
        else:
            result.priority = resume.effective_priority
            result.provenance.extend(resume.provenance)
            result.reasons.extend(resume.reasons)
        if isinstance(spec, ObjectAdmissionPolicySpec):
            if result.priority is None or result.priority <= 0:
                raise ValueError("object stages require resolved positive priority")
            reader = PolicyReader(sources, facts, ObjectAdmissionFacts(effective_priority=KnownFact(value=result.priority)))
            if resume is None:
                stopped = result.stop(evaluate_stage(tuple(r for r in spec.rules
                    if not isinstance(r.effect, SelectPriorityDefaultEffect)), PolicyStage.PRIORITY, reader))
                if stopped is not None:
                    return stopped
        stopped = result.stop(evaluate_stage(spec.rules, PolicyStage.SUPPORT, reader))
        if stopped is not None:
            return stopped
        behavior_stage = evaluate_stage(spec.rules, PolicyStage.BEHAVIOR, reader)
        stopped = result.stop(behavior_stage)
        if stopped is not None:
            return stopped
        choices = selection_rules(behavior_stage)
        result.provenance.extend(rule_provenance(r) for r in choices)
        values = {r.effect.value for r in choices if isinstance(r.effect, SelectBehaviorEffect)}
        if len(values) > 1:
            return result.failure((PolicyProblem(PolicyIssueReason.RULE_CONFLICT, tuple(
                issue(PolicyIssueReason.RULE_CONFLICT, ("rules", r.id),
                      "equal-precedence behavior selections conflict") for r in choices)),))
        if not values and isinstance(spec, ValueSelectionPolicySpec):
            return result.failure((PolicyProblem(PolicyIssueReason.RULE_NO_MATCH, (
                issue(PolicyIssueReason.RULE_NO_MATCH, (), "required behavior has no matching rule"),)),))
        result.reasons.extend(PolicyReason[R](domain_reason=r.domain_reason,
            common_reason=PolicyDisableReason.DOMAIN_RULE) for r in choices if r.domain_reason is not None)
        return result.decision(PolicyState.READY, behavior=next(iter(values), None))
