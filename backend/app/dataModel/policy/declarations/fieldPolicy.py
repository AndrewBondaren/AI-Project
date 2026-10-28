"""Field-local gate and scalar cases; no self-field references (tz_policy §2.2)."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from app.dataModel.policy.declarations.policyDeclaration import AdmissionPolicy, PolicyDescriptor, ValuePolicy
from app.dataModel.policy.declarations.policyIdentity import PolicyScalar, ValueBranch
from app.dataModel.policy.policyEnums import RulePrecedence
from app.dataModel.policy.policyFacts import _policy_value
from app.dataModel.policy.policyRules import _PRECEDENCE

T = TypeVar("T", bound=PolicyScalar)
B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


@dataclass(frozen=True)
class EnabledFor(Generic[B, R]):
    policy: PolicyDescriptor[B, R]

    def __post_init__(self) -> None:
        if not isinstance(self.policy, (ValuePolicy, AdmissionPolicy)):
            raise ValueError("enabled metadata requires policy descriptor")


@dataclass(frozen=True, kw_only=True)
class ValueCase(Generic[T, B, R]):
    when: T
    behavior: B
    reason: R | None = None
    precedence: RulePrecedence | None = None

    def __post_init__(self) -> None:
        ValueBranch(self.when)
        if not isinstance(self.behavior, Enum) or (self.reason is not None and not isinstance(self.reason, Enum)):
            raise ValueError("value case requires behavior/reason enums")
        _policy_value(self.behavior)
        _policy_value(self.reason)
        if self.precedence is not None:
            _PRECEDENCE.validate_python(self.precedence, strict=True)


@dataclass(frozen=True)
class SelectByValue(Generic[T, B, R]):
    policy: PolicyDescriptor[B, R]
    cases: tuple[ValueCase[T, B, R], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.policy, (ValuePolicy, AdmissionPolicy)):
            raise ValueError("selection metadata requires policy descriptor")
        if not isinstance(self.cases, tuple) or not self.cases or any(not isinstance(c, ValueCase) for c in self.cases):
            raise ValueError("selection requires nonempty immutable value cases")
        if len({ValueBranch(case.when) for case in self.cases}) != len(self.cases):
            raise ValueError("duplicate typed value case")
        for case in self.cases:
            if type(case.behavior) is not self.policy.behavior_type:
                raise ValueError("foreign value case behavior enum")
            if case.reason is not None and type(case.reason) is not self.policy.reason_type:
                raise ValueError("foreign value case reason enum")
