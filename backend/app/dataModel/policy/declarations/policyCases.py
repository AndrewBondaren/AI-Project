"""Typed compound declarations over existing policy predicates/effects (tz_policy §2.3)."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from app.dataModel.policy.policyEnums import PolicyStage, RulePrecedence
from app.dataModel.policy.policyFacts import _policy_value
from app.dataModel.policy.policyRules import (
    DisableEffect, Equal, InSet, IsPresent, PolicyPredicate, PriorityDefaultSelection,
    RequireSupportEffect, SelectBehaviorEffect, SelectPriorityDefaultEffect, _PRECEDENCE,
)

B = TypeVar("B", bound=Enum)
R = TypeVar("R", bound=Enum)


@dataclass(frozen=True, kw_only=True)
class PolicyCaseDeclaration(Generic[B, R]):
    key: Enum
    conditions: tuple[PolicyPredicate, ...]
    effect: DisableEffect | PriorityDefaultSelection | RequireSupportEffect | SelectBehaviorEffect[B]
    reason: R | None = None
    precedence: RulePrecedence | None = None
    stage: PolicyStage | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, Enum):
            raise ValueError("compound case requires enum key")
        _policy_value(self.key)
        if not isinstance(self.conditions, tuple) or any(
                not isinstance(p, (Equal, InSet, IsPresent)) for p in self.conditions):
            raise ValueError("compound case requires immutable declared predicates")
        if self.reason is not None and not isinstance(self.reason, Enum):
            raise ValueError("compound case reason requires enum")
        _policy_value(self.reason)
        if isinstance(self.effect, SelectBehaviorEffect):
            _policy_value(self.effect.value)
        if self.precedence is not None:
            _PRECEDENCE.validate_python(self.precedence, strict=True)
        if self.stage is not None and not isinstance(self.stage, PolicyStage):
            raise ValueError("case stage requires PolicyStage")
        inferred = self.effective_stage
        if self.stage is not None and self.stage is not inferred:
            raise ValueError("case stage does not match effect")

    @property
    def effective_stage(self) -> PolicyStage:
        if isinstance(self.effect, DisableEffect):
            if self.stage is None:
                raise ValueError("disable case requires explicit stage")
            return self.stage
        if isinstance(self.effect, SelectBehaviorEffect):
            return PolicyStage.BEHAVIOR
        if isinstance(self.effect, RequireSupportEffect):
            return PolicyStage.SUPPORT
        if isinstance(self.effect, SelectPriorityDefaultEffect):
            return PolicyStage.PRIORITY
        raise ValueError("compound case requires existing policy effect")
