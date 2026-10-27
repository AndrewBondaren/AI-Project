"""Common admission declarations; there is no policy execution in this module."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.placement.common import Specificity
from app.dataModel.policy.policyEnums import (
    PolicyDisableReason, PolicyIssueReason, PolicyOperation, PolicyRuleId, PolicyStage, RulePrecedence,
)
from app.dataModel.policy.policySpec import (
    DirectValueRef, DisableEffect, Equal, FactValue, FactValueRef, ObjectAdmissionPolicySpec,
    PolicyFallback, PolicyReference, PolicyRule, PriorityReference,
)


B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)
M = TypeVar("M", bound=BaseModel)


class PlacementPolicyDefaults(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    placement_specificity: Specificity = Field(default=0, le=0)

    @classmethod
    def canonical_defaults(cls) -> "PlacementPolicyDefaults":
        return cls()


class ObjectAdmissionFacts(BaseModel):
    """The executor's computed priority, never an additional authored priority."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")
    effective_priority: FactValue[Specificity]


class EnabledGateDeclaration(Protocol):
    @property
    def reference(self) -> PolicyReference: ...

    @property
    def is_enabled_gate(self) -> Literal[True]: ...


@dataclass(frozen=True)
class EnabledGate(Generic[M]):
    reference: DirectValueRef[M, bool]

    def __post_init__(self) -> None:
        if not isinstance(self.reference, DirectValueRef):
            raise ValueError("enabled gate requires direct boolean FieldRef")
        bound = self.reference.bound_field
        if bound.model.model_fields[bound.field].annotation is not bool:
            raise ValueError("enabled gate requires boolean field")

    @property
    def is_enabled_gate(self) -> Literal[True]:
        return True


@dataclass(frozen=True)
class ObjectAdmissionBindings(Generic[B, R]):
    enabled_gates: tuple[EnabledGateDeclaration, ...]
    authored_priority_ref: PriorityReference
    domain_priority_ref: PriorityReference
    terminal_priority_ref: PriorityReference
    expected_behavior_type: type[B]
    rules: tuple[PolicyRule[B, R], ...] = ()
    fallback_rules: tuple[PolicyFallback[B], ...] = ()


class ObjectAdmissionPolicyDefinition:
    @staticmethod
    def build(bindings: ObjectAdmissionBindings[B, R]) -> ObjectAdmissionPolicySpec[B, R]:
        if not isinstance(bindings.enabled_gates, tuple):
            raise ValueError("enabled gates require tuple")
        rules: list[PolicyRule[B, R]] = []
        for gate in bindings.enabled_gates:
            if not isinstance(gate, EnabledGate):
                raise ValueError("enabled gates require typed EnabledGate bindings")
            ref = gate.reference
            bound = ref.bound_field
            if bound.model.model_fields[bound.field].annotation is not bool:
                raise ValueError("enabled gate requires strict bool field")
            rules.append(PolicyRule(
                id=PolicyRuleId(f"admission.enabled.{bound.model.__module__}.{bound.model.__qualname__}.{bound.field}"),
                stage=PolicyStage.ABSOLUTE_GATE, precedence=RulePrecedence(0),
                conditions=(Equal(ref, False),), effect=DisableEffect(PolicyDisableReason.ENABLED_FALSE)))
        zero = FactValueRef(FieldRef(lambda: ObjectAdmissionFacts, lambda facts: facts.effective_priority))
        rules.append(PolicyRule(id=PolicyRuleId("admission.zero_priority"),
            stage=PolicyStage.PRIORITY, precedence=RulePrecedence(0),
            conditions=(Equal(zero, 0),), effect=DisableEffect(PolicyDisableReason.ZERO_PRIORITY)))
        reasons = {fallback.reason for fallback in bindings.fallback_rules}
        fallbacks = bindings.fallback_rules
        if PolicyIssueReason.UNKNOWN_FACT not in reasons:
            fallbacks += (PolicyFallback(reason=PolicyIssueReason.UNKNOWN_FACT, behavior=None, disable_object=True),)
        return ObjectAdmissionPolicySpec(operation=PolicyOperation.OBJECT_ADMISSION,
            rules=tuple(rules) + bindings.rules,
            authored_priority_ref=bindings.authored_priority_ref,
            domain_priority_ref=bindings.domain_priority_ref,
            terminal_priority_ref=bindings.terminal_priority_ref,
            expected_behavior_type=bindings.expected_behavior_type,
            fallback_rules=fallbacks)
