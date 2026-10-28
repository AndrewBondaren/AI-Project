"""Lower verified declarations to existing specs; never resolve policy values (tz_policy §4)."""

from enum import Enum
from typing import TypeVar

from pydantic import BaseModel

from app.application.policy.declarations.verify import VerifiedPolicy, verify_policy
from app.dataModel.policy.declarations.policyDeclaration import AdmissionPolicy, PolicyDescriptor, ValuePolicy
from app.dataModel.policy.declarations.policyIdentity import RuleIdentity, RuleKind, ValueBranch, make_rule_id
from app.dataModel.policy.objectAdmissionPolicyDefinition import ObjectAdmissionBindings, ObjectAdmissionPolicyDefinition
from app.dataModel.policy.policyEnums import PolicyOperation, PolicyStage
from app.dataModel.policy.policyRules import Equal, PolicyRule, SelectBehaviorEffect
from app.dataModel.policy.policySpec import ObjectAdmissionPolicySpec, ValueSelectionPolicySpec

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


def _rules(policy: PolicyDescriptor[B, R], verified: VerifiedPolicy[B, R]) -> tuple[PolicyRule[B, R], ...]:
    rules: list[PolicyRule[B, R]] = []
    for selection in verified.selections:
        for case in selection.cases:
            rules.append(PolicyRule(
                id=make_rule_id(RuleIdentity(owner=policy.owner, kind=RuleKind.VALUE_CASE,
                    field=selection.field, branch=ValueBranch(case.when))),
                stage=PolicyStage.BEHAVIOR,
                precedence=case.precedence if case.precedence is not None else policy.default_precedence,
                conditions=(Equal(selection.reference, case.when),),
                effect=SelectBehaviorEffect(case.behavior), domain_reason=case.reason))
    for case in policy.cases:
        rules.append(PolicyRule(
            id=make_rule_id(RuleIdentity(owner=policy.owner, kind=RuleKind.COMPOSITE_CASE, case_key=case.key)),
            stage=case.effective_stage,
            precedence=case.precedence if case.precedence is not None else policy.default_precedence,
            conditions=case.conditions, effect=case.effect, domain_reason=case.reason))
    return tuple(sorted(rules, key=lambda rule: rule.id))


def compile_value_policy(policy: ValuePolicy[B, R], models: tuple[type[BaseModel], ...]) -> ValueSelectionPolicySpec[B, R]:
    if not isinstance(policy, ValuePolicy):
        raise ValueError("value compilation requires ValuePolicy")
    verified = verify_policy(policy, models)
    return ObjectAdmissionPolicyDefinition.bind_value_selection(
        ValueSelectionPolicySpec(operation=PolicyOperation.VALUE_SELECTION, rules=_rules(policy, verified),
            expected_behavior_type=policy.behavior_type, fallback_rules=policy.fallback_rules,
            disabled_behavior=policy.disabled_behavior), enabled_gates=verified.gates, owner=policy.owner)


def compile_admission_policy(policy: AdmissionPolicy[B, R], models: tuple[type[BaseModel], ...]) -> ObjectAdmissionPolicySpec[B, R]:
    if not isinstance(policy, AdmissionPolicy):
        raise ValueError("admission compilation requires AdmissionPolicy")
    verified = verify_policy(policy, models)
    return ObjectAdmissionPolicyDefinition.build(ObjectAdmissionBindings(
        owner=policy.owner, enabled_gates=verified.gates, rules=_rules(policy, verified),
        expected_behavior_type=policy.behavior_type, fallback_rules=policy.fallback_rules,
        authored_priority_ref=policy.authored_priority_ref, domain_priority_ref=policy.domain_priority_ref,
        terminal_priority_ref=policy.terminal_priority_ref))
