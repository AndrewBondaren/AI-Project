"""Operation-specific policy specifications and declaration consistency checks."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Literal, TypeAlias, TypeVar, Union

from app.dataModel.policy.policyEnums import PolicyOperation, PolicyStage
from app.dataModel.policy.policyReferences import PriorityReference, PriorityValueRef
from app.dataModel.policy.policyRules import PolicyFallback, PolicyRule, SelectBehaviorEffect

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


def _spec(rules: tuple[PolicyRule[B, R], ...], fallbacks: tuple[PolicyFallback[B], ...], behavior: type[B]) -> None:
    if not isinstance(behavior, type) or not issubclass(behavior, Enum):
        raise ValueError("spec requires behavior enum type")
    if not isinstance(rules, tuple) or not isinstance(fallbacks, tuple):
        raise ValueError("spec rules/fallbacks require tuples")
    if len({rule.id for rule in rules}) != len(rules):
        raise ValueError("duplicate policy rule id")
    if len({fallback.reason for fallback in fallbacks}) != len(fallbacks):
        raise ValueError("duplicate fallback reason")
    if len({type(rule.domain_reason) for rule in rules if rule.domain_reason is not None}) > 1:
        raise ValueError("mixed domain reason enums")
    for rule in rules:
        if isinstance(rule.effect, SelectBehaviorEffect) and type(rule.effect.value) is not behavior:
            raise ValueError("foreign behavior enum in rule")
    for fallback in fallbacks:
        if fallback.behavior is not None and type(fallback.behavior) is not behavior:
            raise ValueError("foreign behavior enum in fallback")


@dataclass(frozen=True)
class ObjectAdmissionPolicySpec(Generic[B, R]):
    operation: Literal[PolicyOperation.OBJECT_ADMISSION]
    rules: tuple[PolicyRule[B, R], ...]
    authored_priority_ref: PriorityReference
    domain_priority_ref: PriorityReference
    terminal_priority_ref: PriorityReference
    expected_behavior_type: type[B]
    fallback_rules: tuple[PolicyFallback[B], ...]

    def __post_init__(self) -> None:
        if self.operation is not PolicyOperation.OBJECT_ADMISSION:
            raise ValueError("object admission spec cannot become value selection")
        for ref in (self.authored_priority_ref, self.domain_priority_ref, self.terminal_priority_ref):
            if not isinstance(ref, PriorityValueRef):
                raise ValueError("admission requires typed priority refs")
        _spec(self.rules, self.fallback_rules, self.expected_behavior_type)


@dataclass(frozen=True)
class ValueSelectionPolicySpec(Generic[B, R]):
    operation: Literal[PolicyOperation.VALUE_SELECTION]
    rules: tuple[PolicyRule[B, R], ...]
    expected_behavior_type: type[B]
    fallback_rules: tuple[PolicyFallback[B], ...]
    disabled_behavior: B | None = None

    def __post_init__(self) -> None:
        if self.operation is not PolicyOperation.VALUE_SELECTION:
            raise ValueError("value selection requires its operation tag")
        if any(rule.stage is PolicyStage.PRIORITY for rule in self.rules):
            raise ValueError("value selection has no priority stage")
        _spec(self.rules, self.fallback_rules, self.expected_behavior_type)
        if self.disabled_behavior is not None and type(self.disabled_behavior) is not self.expected_behavior_type:
            raise ValueError("foreign disabled behavior enum")


PolicySpec: TypeAlias = Union[ObjectAdmissionPolicySpec[B, R], ValueSelectionPolicySpec[B, R]]
