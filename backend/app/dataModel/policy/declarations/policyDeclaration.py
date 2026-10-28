"""Frozen domain policy descriptors, without executable rules (tz_policy §2.1)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.policy.declarations.policyCases import PolicyCaseDeclaration
from app.dataModel.policy.policyEnums import PolicyStage, RulePrecedence
from app.dataModel.policy.policyFacts import _policy_value
from app.dataModel.policy.policyReferences import PriorityReference, PriorityValueRef
from app.dataModel.policy.policyRules import PolicyFallback, SelectBehaviorEffect, _PRECEDENCE

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


class PolicyOwner:
    """Nominal identity; independent policies can share the same output enum."""


def validate_policy_owner(owner: type[PolicyOwner]) -> None:
    if not isinstance(owner, type) or not issubclass(owner, PolicyOwner) or owner is PolicyOwner:
        raise ValueError("policy requires nominal PolicyOwner subtype")


class DeclarationDefaults(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True,
                              revalidate_instances="always", validate_default=True)
    precedence: Annotated[RulePrecedence, Field(ge=0, strict=True)] = RulePrecedence(0)


@dataclass(frozen=True, eq=False, kw_only=True)
class _PolicyDeclaration(Generic[B, R]):
    owner: type[PolicyOwner]
    behavior_type: type[B]
    reason_type: type[R]
    fallback_rules: tuple[PolicyFallback[B], ...] = ()
    cases: tuple[PolicyCaseDeclaration[B, R], ...] = ()
    default_precedence: RulePrecedence = field(default_factory=lambda: DeclarationDefaults().precedence)

    def __post_init__(self) -> None:
        validate_policy_owner(self.owner)
        for enum_type in (self.behavior_type, self.reason_type):
            if not isinstance(enum_type, type) or not issubclass(enum_type, Enum):
                raise ValueError("policy requires behavior and reason enum types")
            for member in enum_type:
                _policy_value(member)
        _PRECEDENCE.validate_python(self.default_precedence, strict=True)
        if not isinstance(self.fallback_rules, tuple) or any(
                not isinstance(f, PolicyFallback) for f in self.fallback_rules):
            raise ValueError("policy requires immutable fallback declarations")
        if len({f.reason for f in self.fallback_rules}) != len(self.fallback_rules):
            raise ValueError("duplicate fallback reason")
        if any(f.behavior is not None and type(f.behavior) is not self.behavior_type for f in self.fallback_rules):
            raise ValueError("foreign fallback behavior enum")
        if not isinstance(self.cases, tuple) or any(not isinstance(c, PolicyCaseDeclaration) for c in self.cases):
            raise ValueError("policy requires immutable compound cases")
        if len({(type(c.key), c.key.name) for c in self.cases}) != len(self.cases):
            raise ValueError("duplicate compound case key")
        for case in self.cases:
            if case.reason is not None and type(case.reason) is not self.reason_type:
                raise ValueError("foreign case reason enum")
            if isinstance(case.effect, SelectBehaviorEffect) and type(case.effect.value) is not self.behavior_type:
                raise ValueError("foreign case behavior enum")


@dataclass(frozen=True, eq=False, kw_only=True)
class ValuePolicy(_PolicyDeclaration[B, R]):
    disabled_behavior: B | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.disabled_behavior is not None and type(self.disabled_behavior) is not self.behavior_type:
            raise ValueError("foreign disabled behavior enum")
        if any(case.effective_stage is PolicyStage.PRIORITY for case in self.cases):
            raise ValueError("value policy has no priority stage")


@dataclass(frozen=True, eq=False, kw_only=True)
class AdmissionPolicy(_PolicyDeclaration[B, R]):
    authored_priority_ref: PriorityReference
    domain_priority_ref: PriorityReference
    terminal_priority_ref: PriorityReference

    def __post_init__(self) -> None:
        super().__post_init__()
        if any(not isinstance(ref, PriorityValueRef) for ref in (
                self.authored_priority_ref, self.domain_priority_ref, self.terminal_priority_ref)):
            raise ValueError("admission policy requires typed priority refs")


type PolicyDescriptor[B: Enum, R: Enum] = ValuePolicy[B, R] | AdmissionPolicy[B, R]
