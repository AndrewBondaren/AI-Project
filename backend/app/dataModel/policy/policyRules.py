"""Policy predicates, effects and rule declarations; no rule execution."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Generic, Protocol, TypeVar

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter

from app.dataModel.identity.uid import EntityUid
from app.dataModel.policy.policyEnums import (
    PolicyDisableReason, PolicyIssueReason, PolicyRuleId, PolicyStage, RulePrecedence,
)
from app.dataModel.policy.policyFacts import _policy_value
from app.dataModel.policy.policyReferences import (
    DirectValueRef, FactValueRef, PolicyReference, PolicyValueRef, PriorityReference, PriorityValueRef,
)

M = TypeVar("M", bound=BaseModel)
T = TypeVar("T")
B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)

_RULE_ID = TypeAdapter(Annotated[PolicyRuleId, StringConstraints(min_length=1, pattern=r"^\S(?:.*\S)?$")])
_PRECEDENCE = TypeAdapter(Annotated[RulePrecedence, Field(strict=True, ge=0)])
_UIDS = TypeAdapter(tuple[EntityUid, ...])


class PolicyPredicate(Protocol):
    @property
    def reference(self) -> PolicyReference: ...


def _expected(reference: PolicyReference, value: object) -> None:
    if not isinstance(reference, (DirectValueRef, FactValueRef)):
        raise ValueError("predicate requires direct/fact reference")
    TypeAdapter[object](reference.value_annotation).validate_python(value, strict=True)
    _policy_value(value)


@dataclass(frozen=True)
class Equal(Generic[M, T]):
    reference: PolicyValueRef[M, T]
    expected: T

    def __post_init__(self) -> None:
        _expected(self.reference, self.expected)


@dataclass(frozen=True)
class InSet(Generic[M, T]):
    reference: PolicyValueRef[M, T]
    values: frozenset[T]

    def __post_init__(self) -> None:
        if not isinstance(self.values, frozenset) or not self.values:
            raise ValueError("InSet requires nonempty frozen values")
        for value in self.values:
            _expected(self.reference, value)


@dataclass(frozen=True)
class IsPresent(Generic[M, T]):
    reference: PolicyValueRef[M, T]

    def __post_init__(self) -> None:
        if not isinstance(self.reference, (DirectValueRef, FactValueRef)):
            raise ValueError("predicate requires direct/fact reference")


@dataclass(frozen=True)
class DisableEffect:
    reason: PolicyDisableReason

    def __post_init__(self) -> None:
        if not isinstance(self.reason, PolicyDisableReason):
            raise ValueError("disable effect requires common reason enum")


class PriorityDefaultSelection(Protocol):
    @property
    def ref(self) -> PriorityReference: ...


@dataclass(frozen=True)
class SelectPriorityDefaultEffect(Generic[M]):
    ref: PriorityValueRef[M]

    def __post_init__(self) -> None:
        if not isinstance(self.ref, PriorityValueRef):
            raise ValueError("priority default requires typed priority reference")


@dataclass(frozen=True)
class RequireSupportEffect:
    support_uids: tuple[EntityUid, ...]

    def __post_init__(self) -> None:
        _UIDS.validate_python(self.support_uids, strict=True)
        if not self.support_uids or len(set(self.support_uids)) != len(self.support_uids):
            raise ValueError("support effect requires unique nonempty UIDs")


@dataclass(frozen=True)
class SelectBehaviorEffect(Generic[B]):
    value: B

    def __post_init__(self) -> None:
        if not isinstance(self.value, Enum):
            raise ValueError("behavior effect requires domain enum")


@dataclass(frozen=True)
class PolicyRule(Generic[B, R]):
    id: PolicyRuleId
    stage: PolicyStage
    precedence: RulePrecedence
    conditions: tuple[PolicyPredicate, ...]
    effect: DisableEffect | PriorityDefaultSelection | RequireSupportEffect | SelectBehaviorEffect[B]
    domain_reason: R | None = None

    def __post_init__(self) -> None:
        _RULE_ID.validate_python(self.id, strict=True)
        _PRECEDENCE.validate_python(self.precedence, strict=True)
        if not isinstance(self.stage, PolicyStage) or not isinstance(self.conditions, tuple):
            raise ValueError("rule requires stage enum and tuple conditions")
        if any(not isinstance(condition, (Equal, InSet, IsPresent)) for condition in self.conditions):
            raise ValueError("rule conditions require declared predicates")
        if self.domain_reason is not None and not isinstance(self.domain_reason, Enum):
            raise ValueError("domain reason requires enum")
        stages = ((DisableEffect, tuple(PolicyStage)),
                  (SelectPriorityDefaultEffect, (PolicyStage.PRIORITY,)),
                  (RequireSupportEffect, (PolicyStage.SUPPORT,)),
                  (SelectBehaviorEffect, (PolicyStage.BEHAVIOR,)))
        if not any(isinstance(self.effect, kind) and self.stage in allowed for kind, allowed in stages):
            raise ValueError("effect is not permitted in this policy stage")


@dataclass(frozen=True)
class PolicyFallback(Generic[B]):
    reason: PolicyIssueReason
    behavior: B | None
    disable_object: bool

    def __post_init__(self) -> None:
        if not isinstance(self.reason, PolicyIssueReason) or type(self.disable_object) is not bool:
            raise ValueError("fallback requires reason enum and strict bool")
        if self.behavior is not None and not isinstance(self.behavior, Enum):
            raise ValueError("fallback behavior requires domain enum")
